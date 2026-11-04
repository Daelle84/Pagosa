"""Number entities Atlantic Cozytouch integration."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .hub import Hub
from .sensor import CozytouchSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    try:
        hub = hass.data[DOMAIN][config_entry.entry_id]
    except KeyError:
        _LOGGER.error(
            "%s: cannot initialize number entities: hub not found",
            config_entry.title,
        )
        return

    numbers = []

    if hub.is_overkiz():
        numbers.extend(
            [
                OverkizPagosaTargetTemperatureNumber(
                    coordinator=hub,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                ),
                OverkizPagosaBoostDurationNumber(
                    coordinator=hub,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                ),
                OverkizPagosaAwayDurationNumber(
                    coordinator=hub,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                ),
            ]
        )
    else:
        capabilities = hub.get_capabilities_for_device()

        for capability in capabilities:
            if capability["type"] == "temperature_adjustment_number":
                numbers.append(
                    TemperatureAdjustmentNumber(
                        coordinator=hub,
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                    )
                )
            elif capability["type"] == "temperature_percent_adjustment_number":
                numbers.append(
                    TemperaturePercentAdjustmentNumber(
                        coordinator=hub,
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                    )
                )
            elif capability["type"] == "hours_adjustment_number":
                numbers.append(
                    HoursAdjustmentNumber(
                        coordinator=hub,
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                    )
                )
            elif capability["type"] == "minutes_adjustment_number":
                numbers.append(
                    MinutesAdjustmentNumber(
                        coordinator=hub,
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                    )
                )

    if numbers:
        async_add_entities(numbers, True)


class OverkizPagosaNumberBase(CoordinatorEntity[Hub], NumberEntity):
    """Base class for Pagosa number entities."""

    _attr_has_entity_name = True
    _attr_mode = "slider"

    def __init__(
        self,
        coordinator: Hub,
        config_title: str,
        config_uniq_id: str,
        unique_suffix: str,
    ) -> None:
        """Initialize a Pagosa number entity."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{DOMAIN}_{config_uniq_id}_pagosa_{unique_suffix}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator._deviceId))},
            manufacturer="Sauter",
            model="Pagosa 270L",
            name=config_title,
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return (
            self.coordinator.online
            and self.coordinator.last_update_success
        )


class OverkizPagosaTargetTemperatureNumber(OverkizPagosaNumberBase):
    """Pagosa target temperature controlled through Overkiz."""

    _attr_name = "Température de consigne"
    _attr_icon = "mdi:thermometer-water"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 40
    _attr_native_max_value = 65
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: Hub,
        config_title: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize the Pagosa target temperature entity."""
        super().__init__(
            coordinator,
            config_title,
            config_uniq_id,
            "target_temperature",
        )
        self._attr_native_value = self._read_value()

    def _read_value(self) -> float:
        """Read the target temperature from Overkiz."""
        value = self.coordinator.get_overkiz_state(
            "core:TargetTemperatureState",
            50,
        )
        try:
            return float(value)
        except (TypeError, ValueError):
            return 50.0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the displayed target temperature."""
        self._attr_native_value = self._read_value()
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Send a new target temperature to the Pagosa."""
        new_value = max(40, min(65, value))
        await self.coordinator.set_overkiz_target_temperature(new_value)


class OverkizPagosaBoostDurationNumber(OverkizPagosaNumberBase):
    """Pagosa Boost duration."""

    _attr_name = "Durée Boost"
    _attr_icon = "mdi:rocket-launch"
    _attr_native_min_value = 0
    _attr_native_max_value = 7
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "d"

    def __init__(
        self,
        coordinator: Hub,
        config_title: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize Boost duration."""
        super().__init__(
            coordinator,
            config_title,
            config_uniq_id,
            "boost_duration",
        )
        self._attr_native_value = self._read_value()

    def _read_value(self) -> float:
        """Read Boost duration."""
        value = self.coordinator.get_overkiz_state(
            "core:BoostModeDurationState",
            0,
        )
        try:
            return max(0, min(7, float(value)))
        except (TypeError, ValueError):
            return 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update Boost duration."""
        self._attr_native_value = self._read_value()
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set Boost duration."""
        new_value = int(max(0, min(7, value)))
        await self.coordinator.set_overkiz_boost_duration(new_value)


class OverkizPagosaAwayDurationNumber(OverkizPagosaNumberBase):
    """Pagosa absence duration."""

    _attr_name = "Durée Absence"
    _attr_icon = "mdi:home-export-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 6
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "d"

    def __init__(
        self,
        coordinator: Hub,
        config_title: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize absence duration."""
        super().__init__(
            coordinator,
            config_title,
            config_uniq_id,
            "away_duration",
        )
        self._attr_native_value = self._read_value()

    def _read_value(self) -> float:
        """Read absence duration."""
        value = self.coordinator.get_overkiz_state(
            "io:AwayModeDurationState",
            0,
        )
        try:
            return max(0, min(6, float(value)))
        except (TypeError, ValueError):
            return 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update absence duration."""
        self._attr_native_value = self._read_value()
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set absence duration."""
        new_value = int(max(0, min(6, value)))
        await self.coordinator.set_overkiz_away_duration(new_value)


class TemperatureAdjustmentNumber(NumberEntity, CozytouchSensor):
    """Temperature adjustment class."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a Number entity."""
        capabilityId = capability["capabilityId"]
        super().__init__(
            coordinator=coordinator,
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=f"{DOMAIN}_{config_uniq_id}_number_{str(capabilityId)}",
            name=name,
            icon=icon,
        )
        self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._attr_mode = "auto"
        self._attr_native_step = capability.get("step", 0.5)
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_native_min_value = capability.get("lowest_value", 0)
        self._attr_native_max_value = capability.get("highest_value", 60.0)
        self._native_value = 0

    @property
    def native_value(self) -> float | None:
        """Value of the sensor."""
        return self._native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the value of the sensor from the hub."""
        value = float(
            self.coordinator.get_capability_value(self._capability["capabilityId"])
        )

        if "lowestValueCapabilityId" in self._capability:
            lowestValue = self.coordinator.get_capability_value(
                self._capability["lowestValueCapabilityId"], None
            )
            if lowestValue:
                self._attr_native_min_value = float(lowestValue)

        if "highestValueCapabilityId" in self._capability:
            highestValue = self.coordinator.get_capability_value(
                self._capability["highestValueCapabilityId"], None
            )
            if highestValue:
                self._attr_native_max_value = float(highestValue)

        if value < self._attr_native_min_value:
            value = self._attr_native_min_value
        elif value > self._attr_native_max_value:
            value = self._attr_native_max_value

        self._native_value = value
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        new_value = value
        if new_value < self._attr_native_min_value:
            new_value = self._attr_native_min_value
        elif new_value > self._attr_native_max_value:
            new_value = self._attr_native_max_value

        await self.coordinator.set_capability_value(
            self._capability["capabilityId"],
            str(new_value),
        )


class TemperaturePercentAdjustmentNumber(NumberEntity, CozytouchSensor):
    """Temperature percent adjustment class."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a Number entity."""
        capabilityId = capability["capabilityId"]
        super().__init__(
            coordinator=coordinator,
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=f"{DOMAIN}_{config_uniq_id}_number_{str(capabilityId)}",
            name=name,
            icon=icon,
        )
        self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._attr_mode = "auto"
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = "°C"
        self._native_value = 0

        self._attr_native_min_value = 0.0
        if "temperatureMin" in capability:
            self._attr_native_min_value = capability["temperatureMin"]

        self._attr_native_max_value = 60.0
        if "temperatureMax" in capability:
            self._attr_native_max_value = capability["temperatureMax"]

        self._range = self._attr_native_max_value - self._attr_native_min_value

    @property
    def native_value(self) -> float | None:
        """Value of the sensor."""
        return self._native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the value of the sensor from the hub."""
        valuePercent = float(
            self.coordinator.get_capability_value(self._capability["capabilityId"])
        )

        value = self._attr_native_min_value + (valuePercent * self._range / 100.0)

        if value < self._attr_native_min_value:
            value = self._attr_native_min_value
        elif value > self._attr_native_max_value:
            value = self._attr_native_max_value

        self._native_value = value
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        new_value = value
        if new_value < self._attr_native_min_value:
            new_value = self._attr_native_min_value
        elif new_value > self._attr_native_max_value:
            new_value = self._attr_native_max_value

        valuePercent = (new_value - self._attr_native_min_value) * 100 / self._range

        await self.coordinator.set_capability_value(
            self._capability["capabilityId"],
            str(valuePercent),
        )


class HoursAdjustmentNumber(NumberEntity, CozytouchSensor):
    """Hours adjustment number class."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a Number entity."""
        capabilityId = capability["capabilityId"]
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=f"{DOMAIN}_{config_uniq_id}_number_{str(capabilityId)}",
            coordinator=coordinator,
            name=name,
            icon=icon,
        )
        self._attr_device_class = None
        self._attr_mode = "auto"
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS
        self._attr_native_step = capability.get("step", 1)
        self._attr_native_min_value = capability.get("lowest_value", 0)
        self._attr_native_max_value = capability.get("highest_value", 100)
        self._native_value = 0

    @property
    def native_value(self) -> float | None:
        """Value of the sensor."""
        return self._native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the value of the sensor from the hub."""
        value = (
            float(
                self.coordinator.get_capability_value(self._capability["capabilityId"])
            )
            / 60.0
        )

        if value < self._attr_native_min_value:
            value = self._attr_native_min_value
        elif value > self._attr_native_max_value:
            value = self._attr_native_max_value

        self._native_value = value
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        new_value = value
        if new_value < self._attr_native_min_value:
            new_value = self._attr_native_min_value
        elif new_value > self._attr_native_max_value:
            new_value = self._attr_native_max_value

        await self.coordinator.set_capability_value(
            self._capability["capabilityId"], str(int(new_value * 60))
        )

        await self.coordinator.async_request_refresh()


class MinutesAdjustmentNumber(NumberEntity, CozytouchSensor):
    """Minutes adjustment number class."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a Number entity."""
        capabilityId = capability["capabilityId"]
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=f"{DOMAIN}_{config_uniq_id}_number_{str(capabilityId)}",
            coordinator=coordinator,
            name=name,
            icon=icon,
        )
        self._attr_device_class = None
        self._attr_mode = "auto"
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        self._attr_native_step = capability.get("step", 1)
        self._attr_native_min_value = capability.get("lowest_value", 0)
        self._attr_native_max_value = capability.get("highest_value", 60)
        self._native_value = 0

    @property
    def native_value(self) -> float | None:
        """Value of the sensor."""
        return self._native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the value of the sensor from the hub."""
        value = float(
            self.coordinator.get_capability_value(self._capability["capabilityId"])
        )

        if value < self._attr_native_min_value:
            value = self._attr_native_min_value
        elif value > self._attr_native_max_value:
            value = self._attr_native_max_value

        self._native_value = value
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        new_value = value
        if new_value < self._attr_native_min_value:
            new_value = self._attr_native_min_value
        elif new_value > self._attr_native_max_value:
            new_value = self._attr_native_max_value

        await self.coordinator.set_capability_value(
            self._capability["capabilityId"], str(int(new_value))
        )

        await self.coordinator.async_request_refresh()