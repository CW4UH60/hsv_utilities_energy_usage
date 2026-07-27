"""Sensor platform for HSV Utilities Energy integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnergyDataCoordinator

_LOGGER = logging.getLogger(__name__)

PERIOD_NAMES = {
    "unbilled": "Unbilled",
    "current_bill": "Current Bill",
    "previous_bill": "Previous Bill",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HSV Utilities Energy sensors from a config entry."""
    coordinator: EnergyDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Create sensors for each utility type
    entities: list[SensorEntity] = []

    for utility_type in coordinator.utility_types:
        # Usage sensor
        entities.append(
            EnergyUsageSensor(
                coordinator=coordinator,
                utility_type=utility_type,
                entry=entry,
            )
        )
        # Cost sensor
        entities.append(
            EnergyCostSensor(
                coordinator=coordinator,
                utility_type=utility_type,
                entry=entry,
            )
        )
        for period_key in PERIOD_NAMES:
            entities.extend(
                (
                    BillingPeriodSensor(
                        coordinator=coordinator,
                        utility_type=utility_type,
                        entry=entry,
                        period_key=period_key,
                        data_type="usage",
                    ),
                    BillingPeriodSensor(
                        coordinator=coordinator,
                        utility_type=utility_type,
                        entry=entry,
                        period_key=period_key,
                        data_type="cost",
                    ),
                )
            )

    _LOGGER.info("Adding %d entities for HSV Utilities Energy", len(entities))
    async_add_entities(entities)


class EnergyUsageSensor(CoordinatorEntity[EnergyDataCoordinator], SensorEntity):
    """Sensor for energy usage."""

    def __init__(
        self,
        coordinator: EnergyDataCoordinator,
        utility_type: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.utility_type = utility_type
        self._entry = entry
        self._attr_has_entity_name = True

        # Create unique ID
        self._attr_unique_id = f"{entry.entry_id}_{utility_type.lower()}_usage"

        # Set name
        utility_name = utility_type.capitalize()
        self._attr_name = f"{utility_name} Usage"

        # Set icon based on utility type
        if utility_type == "ELECTRIC":
            self._attr_icon = "mdi:flash"
            self._attr_device_class = SensorDeviceClass.ENERGY
        elif utility_type == "GAS":
            self._attr_icon = "mdi:fire"
            # Home Assistant does not accept 'CCF' for SensorDeviceClass.GAS.
            # Avoid setting a device class to prevent unit validation errors.
            self._attr_device_class = None
        elif utility_type == "WATER":
            self._attr_icon = "mdi:water"
            self._attr_device_class = SensorDeviceClass.WATER
        else:
            self._attr_icon = "mdi:gauge"

        # This entity is a rolling 24-hour window, so it can decrease.
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="HSV Utilities Energy",
            configuration_url="https://hsvutil.smarthub.coop",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor (last 24h of available data)."""
        if not self.coordinator.data:
            return None

        utility_data = self.coordinator.data.get(self.utility_type, {})
        usage_data = utility_data.get("usage", {})
        # Show last 24h of available data (accounts for ~2hr data lag)
        return usage_data.get("last_24h", 0.0)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if not self.coordinator.data:
            return None

        utility_data = self.coordinator.data.get(self.utility_type, {})
        usage_data = utility_data.get("usage", {})
        unit = usage_data.get("unit")
        # Normalize units to HA expected casing
        if unit == "KWH":
            return "kWh"
        if unit == "WH":
            return "Wh"
        return unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        utility_data = self.coordinator.data.get(self.utility_type, {})
        usage_data = utility_data.get("usage", {})

        attrs = {
            "today": usage_data.get("today", 0.0),
            "yesterday": usage_data.get("yesterday", 0.0),
            "utility_type": self.utility_type,
            "window": "last_24_hours",
        }

        last_update = usage_data.get("last_update")
        if last_update:
            attrs["last_update"] = last_update

        data_lag = usage_data.get("data_lag_hours")
        if data_lag is not None:
            attrs["data_lag_hours"] = data_lag

        return attrs


class EnergyCostSensor(CoordinatorEntity[EnergyDataCoordinator], SensorEntity):
    """Sensor for energy cost."""

    def __init__(
        self,
        coordinator: EnergyDataCoordinator,
        utility_type: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.utility_type = utility_type
        self._entry = entry
        self._attr_has_entity_name = True

        # Create unique ID
        self._attr_unique_id = f"{entry.entry_id}_{utility_type.lower()}_cost"

        # Set name
        utility_name = utility_type.capitalize()
        self._attr_name = f"{utility_name} Cost"

        # Set attributes
        self._attr_icon = "mdi:currency-usd"
        self._attr_device_class = SensorDeviceClass.MONETARY
        # This entity is a rolling 24-hour window, so it can decrease.
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "USD"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="HSV Utilities Energy",
            configuration_url="https://hsvutil.smarthub.coop",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor (last 24h of available data)."""
        if not self.coordinator.data:
            return None

        utility_data = self.coordinator.data.get(self.utility_type, {})
        cost_data = utility_data.get("cost", {})
        # Show last 24h of available data (accounts for ~2hr data lag)
        return cost_data.get("last_24h", 0.0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        utility_data = self.coordinator.data.get(self.utility_type, {})
        cost_data = utility_data.get("cost", {})

        attrs = {
            "today": cost_data.get("today", 0.0),
            "yesterday": cost_data.get("yesterday", 0.0),
            "utility_type": self.utility_type,
            "window": "last_24_hours",
        }

        last_update = cost_data.get("last_update")
        if last_update:
            attrs["last_update"] = last_update

        return attrs


class BillingPeriodSensor(CoordinatorEntity[EnergyDataCoordinator], SensorEntity):
    """SmartHub usage or cost for an exact utility billing period."""

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: EnergyDataCoordinator,
        utility_type: str,
        entry: ConfigEntry,
        period_key: str,
        data_type: str,
    ) -> None:
        """Initialize a billing-period sensor."""
        super().__init__(coordinator)
        self.utility_type = utility_type
        self._entry = entry
        self.period_key = period_key
        self.data_type = data_type
        self._attr_has_entity_name = True
        self._attr_unique_id = (
            f"{entry.entry_id}_{utility_type.lower()}_{period_key}_{data_type}"
        )

        utility_name = utility_type.capitalize()
        period_name = PERIOD_NAMES[period_key]
        data_name = "Usage" if data_type == "usage" else "Cost"
        self._attr_name = f"{utility_name} {period_name} {data_name}"

        if data_type == "cost":
            self._attr_icon = "mdi:currency-usd"
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = "USD"
        else:
            self._attr_icon = "mdi:meter-electric"
            if utility_type == "ELECTRIC":
                self._attr_device_class = SensorDeviceClass.ENERGY
            elif utility_type == "WATER":
                self._attr_device_class = SensorDeviceClass.WATER

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="HSV Utilities Energy",
            configuration_url="https://hsvutil.smarthub.coop",
        )

    def _period_data(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        utility_data = self.coordinator.data.get(self.utility_type, {})
        return utility_data.get("billing_periods", {}).get(self.period_key, {})

    @property
    def native_value(self) -> float | None:
        """Return the total for this billing period."""
        return self._period_data().get(self.data_type, {}).get("value")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return a normalized unit."""
        if self.data_type == "cost":
            return "USD"
        unit = self._period_data().get(self.data_type, {}).get("unit")
        if unit == "KWH":
            return "kWh"
        if unit == "WH":
            return "Wh"
        return unit

    @property
    def last_reset(self) -> datetime | None:
        """Return the exact beginning of the SmartHub period."""
        value = self._period_data().get("period_start_timestamp")
        return datetime.fromisoformat(value) if value else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return billing dates and source freshness."""
        period_data = self._period_data()
        if not period_data:
            return {}

        utility_data = self.coordinator.data.get(self.utility_type, {})
        freshness = utility_data.get("usage", {})
        return {
            "utility_type": self.utility_type,
            "period": self.period_key,
            "period_status": "open" if period_data.get("is_open") else "closed",
            "period_start": period_data.get("period_start"),
            "period_end": period_data.get("period_end"),
            "period_end_exclusive_timestamp": period_data.get(
                "period_end_exclusive_timestamp"
            ),
            "data_through": freshness.get("last_update"),
            "data_lag_hours": freshness.get("data_lag_hours"),
            "source": period_data.get("source"),
        }
