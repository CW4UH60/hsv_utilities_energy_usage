from datetime import datetime, timezone

from component_loader import load_component_module

billing_periods = load_component_module("billing_periods")


def api_timestamp(year, month, day):
    """Encode a SmartHub Central wall-clock date as a UTC timestamp."""
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)


UNBILLED_X = api_timestamp(9999, 12, 1)
CURRENT_X = api_timestamp(2026, 6, 2)
PREVIOUS_X = api_timestamp(2026, 5, 4)

INTERVALS = {
    str(UNBILLED_X): {
        "orderedName": "Dec 9999",
        "interval": {
            "start": api_timestamp(2026, 7, 2),
            "end": api_timestamp(9999, 12, 31),
        },
    },
    str(CURRENT_X): {
        "orderedName": "Jun 2026",
        "interval": {
            "start": api_timestamp(2026, 6, 2),
            "end": api_timestamp(2026, 7, 2),
        },
    },
    str(PREVIOUS_X): {
        "orderedName": "May 2026",
        "interval": {
            "start": api_timestamp(2026, 5, 4),
            "end": api_timestamp(2026, 6, 2),
        },
    },
}


def monthly_payload():
    return {
        "status": "COMPLETE",
        "data": {
            "ELECTRIC": [
                {
                    "type": "USAGE",
                    "unitOfMeasure": "KWH",
                    "xToOrderedInterval": INTERVALS,
                    "series": [
                        {
                            "meterNumber": "meter-a",
                            "data": [
                                {"x": UNBILLED_X, "y": 3000.0},
                                {"x": CURRENT_X, "y": 4000.0},
                                {"x": PREVIOUS_X, "y": 3400.0},
                            ],
                        },
                        {
                            "meterNumber": "meter-b",
                            "data": [
                                {"x": UNBILLED_X, "y": 697.23},
                                {"x": CURRENT_X, "y": 123.45},
                                {"x": PREVIOUS_X, "y": 100.0},
                            ],
                        },
                    ],
                },
                {
                    "type": "COST",
                    "unitOfMeasure": "USD",
                    "xToOrderedInterval": INTERVALS,
                    "series": [
                        {
                            "meterNumber": "meter-a",
                            "data": [
                                {"x": UNBILLED_X, "y": 440.35},
                                {"x": CURRENT_X, "y": 510.2},
                                {"x": PREVIOUS_X, "y": 430.0},
                            ],
                        }
                    ],
                },
            ]
        },
    }


def test_extracts_unbilled_and_two_latest_closed_periods():
    result = billing_periods.extract_billing_periods(monthly_payload(), "ELECTRIC")

    assert list(result) == ["unbilled", "current_bill", "previous_bill"]

    unbilled = result["unbilled"]
    assert unbilled["is_open"] is True
    assert unbilled["period_start"] == "2026-07-02"
    assert unbilled["period_end"] is None
    assert unbilled["period_start_timestamp"] == "2026-07-02T05:00:00+00:00"
    assert unbilled["usage"] == {"value": 3697.23, "unit": "KWH"}
    assert unbilled["cost"] == {"value": 440.35, "unit": "USD"}

    current = result["current_bill"]
    assert current["period_start"] == "2026-06-02"
    assert current["period_end"] == "2026-07-01"
    assert current["period_end_exclusive_timestamp"] == ("2026-07-02T05:00:00+00:00")
    assert current["usage"]["value"] == 4123.45

    previous = result["previous_bill"]
    assert previous["period_start"] == "2026-05-04"
    assert previous["period_end"] == "2026-06-01"
    assert previous["usage"]["value"] == 3500.0


def test_returns_empty_when_monthly_metadata_is_missing():
    payload = {
        "data": {
            "ELECTRIC": [
                {
                    "type": "USAGE",
                    "unitOfMeasure": "KWH",
                    "series": [],
                }
            ]
        }
    }

    assert billing_periods.extract_billing_periods(payload, "ELECTRIC") == {}
