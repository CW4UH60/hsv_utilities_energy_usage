import asyncio
import logging

import aiohttp

from custom_components.hsv_utilities_energy import api_client
from custom_components.hsv_utilities_energy.api_client import UtilityAPIClient
from custom_components.hsv_utilities_energy.const import DEFAULT_REQUEST_TIMEOUT


class FakeResponse:
    def __init__(self, status, payload=None, json_error=None):
        self.status = status
        self._payload = payload if payload is not None else {}
        self._json_error = json_error

    async def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


class FakeRequestContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSession:
    def __init__(self, responses=None, exception=None):
        self.headers = {}
        self.responses = list(responses or [])
        self.exception = exception
        self.calls = []
        self.closed = False

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self.exception:
            raise self.exception
        if not self.responses:
            raise AssertionError("No fake response queued")
        return FakeRequestContext(self.responses.pop(0))

    async def close(self):
        self.closed = True


def run(coro):
    return asyncio.run(coro)


def complete_usage_payload():
    return {
        "status": "COMPLETE",
        "data": {
            "ELECTRIC": [
                {
                    "type": "USAGE",
                    "unitOfMeasure": "KWH",
                    "series": [
                        {
                            "meterNumber": "555444333",
                            "data": [{"x": 1783296000000, "y": 1.25}],
                        }
                    ],
                }
            ]
        },
    }


def assert_timeout(call, total=DEFAULT_REQUEST_TIMEOUT):
    assert isinstance(call["timeout"], aiohttp.ClientTimeout)
    assert call["timeout"].total == total


def test_authenticate_success_sets_bearer_header_and_timeout():
    session = FakeSession([FakeResponse(200, {"authorizationToken": "tok-secret"})])
    client = UtilityAPIClient("person@example.com", "password-secret", session=session)

    assert run(client.authenticate()) is True

    assert client.access_token == "tok-secret"
    assert session.headers["Authorization"] == "Bearer tok-secret"
    assert session.calls[0]["data"] == {
        "userId": "person@example.com",
        "password": "password-secret",
    }
    assert_timeout(session.calls[0])


def test_authenticate_failure_logs_status_without_body_or_password(caplog):
    session = FakeSession([FakeResponse(401, {"error": "password-secret"})])
    client = UtilityAPIClient("person@example.com", "password-secret", session=session)

    with caplog.at_level(logging.ERROR, logger=api_client.__name__):
        assert run(client.authenticate()) is False

    assert "status=401" in caplog.text
    assert "password-secret" not in caplog.text
    assert "person@example.com" not in caplog.text


def test_authenticate_exception_is_redacted_without_traceback(caplog):
    session = FakeSession(
        exception=RuntimeError(
            "Bearer abc.def.ghi person@example.com account 123456789 "
            "password=super-secret"
        )
    )
    client = UtilityAPIClient("person@example.com", "super-secret", session=session)

    with caplog.at_level(logging.ERROR, logger=api_client.__name__):
        assert run(client.authenticate()) is False

    assert "abc.def.ghi" not in caplog.text
    assert "person@example.com" not in caplog.text
    assert "123456789" not in caplog.text
    assert "super-secret" not in caplog.text
    assert "Traceback" not in caplog.text


def test_get_usage_data_defaults_to_electric_and_uses_timeout():
    payload = complete_usage_payload()
    session = FakeSession([FakeResponse(200, payload)])
    client = UtilityAPIClient("person@example.com", "password-secret", session=session)

    result = run(
        client.get_usage_data(
            service_location_number="987654321",
            account_number="123456789",
            start_datetime=1783296000000,
            end_datetime=1783382400000,
        )
    )

    assert result == payload
    assert session.calls[0]["json"]["industries"] == ["ELECTRIC"]
    assert session.calls[0]["json"]["serviceLocationNumber"] == "987654321"
    assert session.calls[0]["json"]["accountNumber"] == "123456789"
    assert_timeout(session.calls[0])


def test_get_usage_data_polls_pending_until_complete(monkeypatch):
    sleep_delays = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)

    monkeypatch.setattr(api_client.asyncio, "sleep", fake_sleep)
    session = FakeSession(
        [
            FakeResponse(200, {"status": "PENDING"}),
            FakeResponse(200, complete_usage_payload()),
        ]
    )
    client = UtilityAPIClient("person@example.com", "password-secret", session=session)

    result = run(
        client.get_usage_data(
            service_location_number="987654321",
            account_number="123456789",
            start_datetime=1783296000000,
            end_datetime=1783382400000,
            max_retries=2,
            retry_delay=7,
        )
    )

    assert result == complete_usage_payload()
    assert len(session.calls) == 2
    assert sleep_delays == [7]


def test_get_usage_data_returns_none_when_pending_exhausts():
    session = FakeSession([FakeResponse(200, {"status": "PENDING"})])
    client = UtilityAPIClient("person@example.com", "password-secret", session=session)

    result = run(
        client.get_usage_data(
            service_location_number="987654321",
            account_number="123456789",
            start_datetime=1783296000000,
            end_datetime=1783382400000,
            max_retries=0,
        )
    )

    assert result is None


def test_get_usage_data_failure_logs_status_without_sensitive_payload(caplog):
    session = FakeSession([FakeResponse(500, {"accountNumber": "123456789"})])
    client = UtilityAPIClient("person@example.com", "password-secret", session=session)

    with caplog.at_level(logging.ERROR, logger=api_client.__name__):
        result = run(
            client.get_usage_data(
                service_location_number="987654321",
                account_number="123456789",
                start_datetime=1783296000000,
                end_datetime=1783382400000,
            )
        )

    assert result is None
    assert "status=500" in caplog.text
    assert "123456789" not in caplog.text
    assert "987654321" not in caplog.text
    assert "password-secret" not in caplog.text


def test_get_usage_data_json_error_is_redacted(caplog):
    session = FakeSession(
        [
            FakeResponse(
                200,
                json_error=ValueError(
                    "accountNumber=123456789 serviceLocationNumber=987654321 "
                    "password=super-secret"
                ),
            )
        ]
    )
    client = UtilityAPIClient("person@example.com", "super-secret", session=session)

    with caplog.at_level(logging.ERROR, logger=api_client.__name__):
        result = run(
            client.get_usage_data(
                service_location_number="987654321",
                account_number="123456789",
                start_datetime=1783296000000,
                end_datetime=1783382400000,
            )
        )

    assert result is None
    assert "123456789" not in caplog.text
    assert "987654321" not in caplog.text
    assert "super-secret" not in caplog.text
    assert "Traceback" not in caplog.text


def test_close_does_not_close_borrowed_session():
    session = FakeSession()
    client = UtilityAPIClient("person@example.com", "password-secret", session=session)

    run(client.close())

    assert session.closed is False
