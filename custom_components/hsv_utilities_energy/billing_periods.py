"""Parse SmartHub billing-period metadata and totals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

UNBILLED_ORDERED_NAME = "Dec 9999"
PERIOD_KEYS = ("unbilled", "current_bill", "previous_bill")
HSV_TIMEZONE = ZoneInfo("America/Chicago")


def extract_billing_periods(
    api_data: dict[str, Any], utility_type: str
) -> dict[str, dict[str, Any]]:
    """Extract open and closed billing periods from a monthly SmartHub response."""
    industry_datasets = api_data.get("data", {}).get(utility_type, [])
    if not isinstance(industry_datasets, list):
        return {}

    records: dict[tuple[int, bool], dict[str, Any]] = {}

    for dataset in industry_datasets:
        if not isinstance(dataset, dict):
            continue

        data_type = str(dataset.get("type", "")).upper()
        if data_type not in {"USAGE", "COST"}:
            continue

        intervals = _normalize_intervals(dataset.get("xToOrderedInterval"))
        if not intervals:
            continue

        point_totals = _aggregate_series_points(dataset.get("series"))
        unit = dataset.get("unitOfMeasure")

        for x_value, interval_info in intervals.items():
            interval = interval_info.get("interval", {})
            start_ms = _as_int(interval.get("start"))
            end_ms = _as_int(interval.get("end"))
            if start_ms is None:
                continue

            ordered_name = str(interval_info.get("orderedName", ""))
            is_open = ordered_name == UNBILLED_ORDERED_NAME or _is_far_future(end_ms)
            record = records.setdefault(
                (start_ms, is_open),
                {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "is_open": is_open,
                    "ordered_name": ordered_name or None,
                    "values": {},
                },
            )

            value = point_totals.get(x_value)
            if value is not None:
                existing_value = record["values"].get(data_type, {}).get("value")
                record["values"][data_type] = {
                    "value": round((existing_value or 0.0) + value, 2),
                    "unit": unit,
                }

    open_periods = sorted(
        (record for record in records.values() if record["is_open"]),
        key=lambda record: record["start_ms"],
        reverse=True,
    )
    closed_periods = sorted(
        (record for record in records.values() if not record["is_open"]),
        key=lambda record: record["start_ms"],
        reverse=True,
    )

    selected: dict[str, dict[str, Any]] = {}
    if open_periods:
        selected["unbilled"] = _serialize_period(open_periods[0], "unbilled")
    if closed_periods:
        selected["current_bill"] = _serialize_period(closed_periods[0], "current_bill")
    if len(closed_periods) > 1:
        selected["previous_bill"] = _serialize_period(
            closed_periods[1], "previous_bill"
        )
    return selected


def _normalize_intervals(value: Any) -> dict[int, dict[str, Any]]:
    """Normalize SmartHub's serialized interval map."""
    result: dict[int, dict[str, Any]] = {}
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = (
            (item.get("x"), item)
            for item in value
            if isinstance(item, dict) and item.get("x") is not None
        )
    else:
        return result

    for raw_key, interval in items:
        key = _as_int(raw_key)
        if key is not None and isinstance(interval, dict):
            result[key] = interval
    return result


def _aggregate_series_points(value: Any) -> dict[int, float]:
    """Sum monthly chart points across all meters."""
    if not isinstance(value, list):
        return {}

    totals: dict[int, float] = {}
    for series in value:
        if not isinstance(series, dict):
            continue
        points = series.get("data", [])
        if not isinstance(points, list):
            continue
        for point in points:
            if not isinstance(point, dict):
                continue
            x_value = _as_int(point.get("x"))
            y_value = point.get("y")
            if x_value is None or not isinstance(y_value, (int, float)):
                continue
            totals[x_value] = totals.get(x_value, 0.0) + float(y_value)
    return totals


def _serialize_period(record: dict[str, Any], period_key: str) -> dict[str, Any]:
    """Convert an internal period record to coordinator data."""
    start_ms = record["start_ms"]
    end_ms = record.get("end_ms")
    is_open = record["is_open"]
    start_utc = _smarthub_timestamp_to_utc(start_ms)

    end_utc = None
    period_end = None
    if not is_open and end_ms is not None:
        end_utc = _smarthub_timestamp_to_utc(end_ms)
        period_end = (_smarthub_wall_date(end_ms) - timedelta(days=1)).isoformat()

    values = record["values"]
    return {
        "period": period_key,
        "is_open": is_open,
        "period_start": _smarthub_wall_date(start_ms).isoformat(),
        "period_end": period_end,
        "period_start_timestamp": start_utc.isoformat(),
        "period_end_exclusive_timestamp": end_utc.isoformat() if end_utc else None,
        "ordered_name": record.get("ordered_name"),
        "usage": values.get("USAGE", {"value": None, "unit": None}),
        "cost": values.get("COST", {"value": None, "unit": None}),
        "source": "smarthub_monthly",
    }


def _smarthub_wall_date(timestamp_ms: int):
    """Return the America/Chicago date represented by an interval timestamp."""
    return (
        datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        .astimezone(HSV_TIMEZONE)
        .date()
    )


def _smarthub_timestamp_to_utc(timestamp_ms: int) -> datetime:
    """Return the real UTC timestamp supplied in billing interval metadata."""
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)


def _is_far_future(timestamp_ms: int | None) -> bool:
    if timestamp_ms is None:
        return False
    return _smarthub_wall_date(timestamp_ms).year >= 9999


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
