"""The HSV Utilities Energy integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from .const import (
    CONF_ACCOUNT_NUMBER,
    CONF_DATA_PATH,
    CONF_FETCH_DAYS,
    CONF_PASSWORD,
    CONF_SERVICE_LOCATION,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    CONF_UTILITY_TYPES,
    DEFAULT_FETCH_DAYS,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_UTILITY_TYPES,
    DOMAIN,
)
from .schemas import (
    ATTR_ENTRY_ID,
    SERVICE_CLEAR_STATISTICS_SCHEMA,
    SERVICE_REFRESH_DATA_SCHEMA,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)

try:
    from homeassistant.const import Platform
except ModuleNotFoundError as err:
    if err.name != "homeassistant":
        raise
    PLATFORMS: list[str] = ["sensor"]
else:
    PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_REFRESH_DATA = "refresh_data"
SERVICE_CLEAR_STATISTICS = "clear_statistics"


def _coordinators_for_service(
    hass: HomeAssistant,
    entry_id: str | None,
) -> list[Any]:
    """Return coordinators targeted by a service call."""
    from homeassistant.exceptions import HomeAssistantError

    coordinators: dict[str, Any] = hass.data.get(DOMAIN, {})

    if entry_id:
        coordinator = coordinators.get(entry_id)
        if coordinator is None:
            raise HomeAssistantError(
                f"No HSV Utilities Energy config entry found for entry_id {entry_id}"
            )
        return [coordinator]

    if len(coordinators) != 1:
        raise HomeAssistantError(
            "Specify entry_id when multiple HSV Utilities Energy entries are loaded"
        )

    return [next(iter(coordinators.values()))]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HSV Utilities Energy from a config entry."""
    from .coordinator import EnergyDataCoordinator

    _LOGGER.info("Setting up HSV Utilities Energy integration")

    # Get configuration
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    service_location_number = entry.data.get(CONF_SERVICE_LOCATION)
    account_number = entry.data.get(CONF_ACCOUNT_NUMBER)
    data_path = entry.data.get(CONF_DATA_PATH)
    update_interval_seconds = entry.data.get(
        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
    )
    fetch_days = entry.data.get(CONF_FETCH_DAYS, DEFAULT_FETCH_DAYS)
    utility_types = entry.data.get(CONF_UTILITY_TYPES, DEFAULT_UTILITY_TYPES)

    # Create coordinator
    coordinator = EnergyDataCoordinator(
        hass=hass,
        username=username,
        password=password,
        service_location_number=service_location_number,
        account_number=account_number,
        data_path=data_path,
        update_interval=timedelta(seconds=update_interval_seconds),
        fetch_days=fetch_days,
        utility_types=utility_types,
        entry_id=entry.entry_id,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register service to manually refresh data
    async def async_refresh_data(call: ServiceCall) -> None:
        """Manually refresh energy data."""
        _LOGGER.info("Manual data refresh requested")
        for target_coordinator in _coordinators_for_service(
            hass,
            call.data.get(ATTR_ENTRY_ID),
        ):
            await target_coordinator.async_request_refresh()

    # Register service to clear and rebuild statistics
    async def async_clear_statistics(call: ServiceCall) -> None:
        """Clear all statistics and rebuild from scratch."""
        _LOGGER.info("Clear statistics requested")
        for target_coordinator in _coordinators_for_service(
            hass,
            call.data.get(ATTR_ENTRY_ID),
        ):
            await target_coordinator.async_clear_statistics()

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH_DATA):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH_DATA,
            async_refresh_data,
            schema=SERVICE_REFRESH_DATA_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_STATISTICS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_STATISTICS,
            async_clear_statistics,
            schema=SERVICE_CLEAR_STATISTICS_SCHEMA,
        )

    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading HSV Utilities Energy integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove coordinator from hass.data
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator is not None:
            await coordinator.async_close()

        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH_DATA)
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_STATISTICS)

    return unload_ok
