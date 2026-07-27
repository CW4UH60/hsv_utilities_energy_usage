import asyncio
from datetime import datetime, timedelta, timezone
import logging

import pytest

from custom_components.hsv_utilities_energy.api_client import UtilityAPIClient
from custom_components.hsv_utilities_energy.billing_periods import (
    extract_billing_periods,
)

pytestmark = pytest.mark.live_smarthub


def test_live_auth_and_electric_usage_shape(live_smarthub_credentials, caplog):
    async def run_live_check():
        async with UtilityAPIClient(
            live_smarthub_credentials["username"],
            live_smarthub_credentials["password"],
        ) as client:
            assert await client.authenticate()

            end_time = datetime.now(tz=timezone.utc)
            start_time = end_time - timedelta(days=1)
            data = await client.get_usage_data(
                service_location_number=live_smarthub_credentials["service_location"],
                account_number=live_smarthub_credentials["account_number"],
                start_datetime=int(start_time.timestamp() * 1000),
                end_datetime=int(end_time.timestamp() * 1000),
                industries=["ELECTRIC"],
                max_retries=5,
                retry_delay=2,
            )

            assert isinstance(data, dict)
            assert "data" in data or "status" in data
            if "data" in data:
                assert isinstance(data["data"], dict)

            monthly_start = end_time - timedelta(days=400)
            monthly_data = await client.get_usage_data(
                service_location_number=live_smarthub_credentials["service_location"],
                account_number=live_smarthub_credentials["account_number"],
                start_datetime=int(monthly_start.timestamp() * 1000),
                end_datetime=int(end_time.timestamp() * 1000),
                time_frame="MONTHLY",
                industries=["ELECTRIC"],
                max_retries=5,
                retry_delay=2,
            )
            assert isinstance(monthly_data, dict)
            periods = extract_billing_periods(monthly_data, "ELECTRIC")
            assert "unbilled" in periods
            assert "current_bill" in periods
            assert periods["unbilled"]["period_start"]
            assert periods["unbilled"]["usage"]["value"] is not None

    with caplog.at_level(logging.INFO):
        asyncio.run(run_live_check())

    _assert_sensitive_values_not_logged(caplog.text, live_smarthub_credentials)


def _assert_sensitive_values_not_logged(log_text, credentials):
    for value in credentials.values():
        assert value not in log_text
