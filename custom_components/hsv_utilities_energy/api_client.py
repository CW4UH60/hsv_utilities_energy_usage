"""API client for HSV Utilities SmartHub."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import aiohttp

from .const import DEFAULT_REQUEST_TIMEOUT, DEFAULT_UTILITY_TYPES
from .redact import redact_for_log


def _build_threaded_connector() -> aiohttp.TCPConnector:
    """Create a connector that avoids aiodns/pycares issues by using threaded resolver."""
    return aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())


def _build_client_session(timeout: aiohttp.ClientTimeout) -> aiohttp.ClientSession:
    """Create a client session with resolver and timeout defaults."""
    return aiohttp.ClientSession(
        connector=_build_threaded_connector(),
        timeout=timeout,
    )


_LOGGER = logging.getLogger(__name__)


class UtilityAPIClient:
    """Async client for interacting with HSV Utility SmartHub API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.base_url = "https://hsvutil.smarthub.coop"
        self.auth_url = f"{self.base_url}/services/oauth/auth/v2"
        self._session = session
        self._own_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self.access_token: Optional[str] = None

    async def __aenter__(self):
        """Async context manager entry."""
        if self._own_session:
            # Use threaded resolver to dodge aiodns Channel.getaddrinfo signature errors in this container
            self._session = _build_client_session(self._timeout)
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        await self.close()

    def _ensure_session(self) -> aiohttp.ClientSession:
        """Return an active session, creating one when this client owns it."""
        if not self._session:
            self._session = _build_client_session(self._timeout)
            self._own_session = True
        return self._session

    async def authenticate(self) -> bool:
        """Authenticate with the utility provider's OAuth endpoint."""
        payload = {"userId": self.username, "password": self.password}

        try:
            _LOGGER.debug("Authenticating with %s", self.auth_url)

            session = self._ensure_session()

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "HomeAssistant-HSV-Utilities/0.1",
            }

            async with session.post(
                self.auth_url,
                data=payload,
                headers=headers,
                timeout=self._timeout,
            ) as response:
                status = response.status

                if status != 200:
                    _LOGGER.error(
                        "Authentication failed. endpoint=auth status=%s",
                        status,
                    )
                    return False

                # Parse JSON if possible
                try:
                    auth_response = await response.json()
                except Exception:
                    _LOGGER.error(
                        "Authentication response was not JSON. endpoint=auth status=%s",
                        status,
                    )
                    return False

                # Extract access token if present (API can return authorizationToken)
                if isinstance(auth_response, dict):
                    self.access_token = (
                        auth_response.get("access_token")
                        or auth_response.get("accessToken")
                        or auth_response.get("authorizationToken")
                        or auth_response.get("authorization_token")
                    )

                if not self.access_token:
                    _LOGGER.error(
                        "Authentication succeeded but no access token in response. keys=%s",
                        redact_for_log(list(auth_response.keys()))
                        if isinstance(auth_response, dict)
                        else type(auth_response).__name__,
                    )
                    return False

                _LOGGER.info("Authentication successful; token obtained")
                session.headers.update({"Authorization": f"Bearer {self.access_token}"})
                return True

        except Exception as err:
            _LOGGER.error("Error during authentication: %s", redact_for_log(err))
            return False

    async def get_usage_data(
        self,
        service_location_number: str,
        account_number: str,
        start_datetime: int,
        end_datetime: int,
        time_frame: str = "HOURLY",
        industries: list[str] | None = None,
        include_demand: bool = False,
        max_retries: int = 10,
        retry_delay: int = 2,
    ) -> dict[str, Any] | None:
        """Retrieve energy usage data from the utility API.

        Args:
            service_location_number: Service location number
            account_number: Account number
            start_datetime: Start time in milliseconds since epoch
            end_datetime: End time in milliseconds since epoch
            time_frame: Time frame for data (HOURLY, DAILY, MONTHLY)
            industries: List of industries to query (WATER, GAS, ELECTRIC)
            include_demand: Whether to include demand data
            max_retries: Maximum number of polling attempts
            retry_delay: Seconds to wait between polling attempts

        Returns:
            Usage data response from API or None on error
        """
        if industries is None:
            industries = list(DEFAULT_UTILITY_TYPES)

        usage_url = f"{self.base_url}/services/secured/utility-usage/poll"

        payload = {
            "timeFrame": time_frame,
            "userId": self.username,
            "screen": "USAGE_EXPLORER",
            "includeDemand": include_demand,
            "serviceLocationNumber": service_location_number,
            "accountNumber": account_number,
            "industries": industries,
            "startDateTime": start_datetime,
            "endDateTime": end_datetime,
        }

        try:
            _LOGGER.debug(
                "Fetching usage data for %s from %s to %s",
                industries,
                start_datetime,
                end_datetime,
            )

            session = self._ensure_session()

            # Initial request
            async with session.post(
                usage_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            ) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to retrieve usage data. endpoint=usage status=%s industries=%s",
                        response.status,
                        redact_for_log(industries),
                    )
                    return None

                data = await response.json()

            # Poll until data is ready
            retry_count = 0
            while data.get("status") == "PENDING" and retry_count < max_retries:
                retry_count += 1
                _LOGGER.debug("Data pending, retry %d/%d", retry_count, max_retries)
                await asyncio.sleep(retry_delay)

                # Poll again
                async with session.post(
                    usage_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self._timeout,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                    else:
                        _LOGGER.error(
                            "Usage polling failed. endpoint=usage status=%s industries=%s",
                            response.status,
                            redact_for_log(industries),
                        )
                        return None

            # Check final status
            if data.get("status") == "PENDING":
                _LOGGER.warning("Data still pending after %d attempts", max_retries)
                return None
            elif (
                data.get("status") == "COMPLETE"
                or "data" in data
                or len(data.keys()) > 1
            ):
                _LOGGER.info("Usage data retrieved successfully")
                return data
            else:
                _LOGGER.warning(
                    "Unexpected response status: %s", data.get("status", "unknown")
                )
                return data

        except Exception as err:
            _LOGGER.error("Error retrieving usage data: %s", redact_for_log(err))
            return None

    async def close(self) -> None:
        """Close the session."""
        if self._own_session and self._session:
            await self._session.close()
        self._session = None
