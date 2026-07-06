from pathlib import Path
import sys

from dotenv import load_dotenv
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_addoption(parser):
    parser.addoption(
        "--run-live-smarthub",
        action="store_true",
        default=False,
        help="Run opt-in tests against the live HSV Utilities SmartHub API.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_smarthub: opt-in tests that call the live HSV Utilities SmartHub API",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live-smarthub"):
        return

    skip_live = pytest.mark.skip(
        reason="live SmartHub tests require --run-live-smarthub"
    )
    for item in items:
        if "live_smarthub" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def live_smarthub_credentials():
    load_dotenv()
    credentials = {
        "username": _env_first("HSV_UTIL_USERNAME", "UTILITY_USERNAME"),
        "password": _env_first("HSV_UTIL_PASSWORD", "UTILITY_PASSWORD"),
        "service_location": _env_first(
            "HSV_UTIL_SERVICE_LOCATION", "SERVICE_LOCATION_NUMBER"
        ),
        "account_number": _env_first("HSV_UTIL_ACCOUNT_NUMBER", "ACCOUNT_NUMBER"),
    }
    missing = [key for key, value in credentials.items() if not value]
    if missing:
        pytest.skip(f"missing live SmartHub credentials: {', '.join(missing)}")
    return credentials


def _env_first(*names: str) -> str | None:
    import os

    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None
