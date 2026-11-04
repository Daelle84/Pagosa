"""Switches for Atlantic Cozytouch and Sauter Pagosa integration."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .hub import Hub
from .sensor import CozytouchSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    try:
        hub = hass.data[DOMAIN][config_entry.entry_id]
    except KeyError:
        _LOGGER.error(
            "%s: cannot initialize switches: hub not found",
            config_entry.title,
        )
        return

    switches = []

    if hub.is_overkiz():
        device = hub.get_overkiz_device()
        if not device:
            _LOGGER.warning("Pagosa Overkiz device not found")
            return

        device_id = str(
            config_entry.data.get("deviceId", config_entry.entry_id)
        )

        common = {
            "coordinator": hub,
            "config_title": config_entry.title,
            "config_device_id": device_id,
            "config_uniq_id": config_entry.entry_id,
        }

        switches.extend(
            [
                PagosaEcoSwitch(**common),
                PagosaBoostSwitch(**common),
                PagosaOperatingModeSwitch(
                    **common,
                    mode_key="absence",
                    name="Mode absence",
                    icon="mdi:home-export-outline",
                ),
            ]
        )
    else:
        capabilities = hub.get_capabilities_for_device()

        for capability in capabilities:
            if capability["type"] == "switch":
                switches.append(
                    CozytouchSwitch(
                        coordinator=hub,
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                    )
                )
            elif capability["type"] == "away_mode_switch":
                switches.append(
                    CozytouchAwayModeSwitch(
                        coordinator=hub,
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                    )
                )

    if switches:
        async_add_entities(switches, True)


class PagosaBaseSwitch(CoordinatorEntity[Hub], SwitchEntity):
    """Base class for Pagosa switches."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Hub,
        name: str,
        icon: str,
        config_title: str,
        config_device_id: str,
        config_uniq_id: str,
        unique_suffix: str,
    ) -> None:
        """Initialize a Pagosa switch."""
        super().__init__(coordinator)

        self._hub = coordinator
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = (
            f"{config_uniq_id}_pagosa_{unique_suffix}"
        )

        device = coordinator.get_overkiz_device() or {}

        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_device_id)},
            "name": device.get("label") or config_title or "Sauter Pagosa 270L",
            "manufacturer": "Sauter",
            "model": "Pagosa 270L",
        }

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._hub.online and self._hub.last_update_success


class PagosaEcoSwitch(PagosaBaseSwitch):
    """Switch for Pagosa Eco mode."""

    def __init__(
        self,
        coordinator: Hub,
        config_title: str,
        config_device_id: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize Eco switch."""
        super().__init__(
            coordinator=coordinator,
            name="Mode Eco",
            icon="mdi:leaf",
            config_title=config_title,
            config_device_id=config_device_id,
            config_uniq_id=config_uniq_id,
            unique_suffix="eco",
        )

    @property
    def is_on(self) -> bool:
        """Return whether Eco mode is active."""
        return (
            self._hub.get_overkiz_state("io:DHWModeState")
            == "manualEcoActive"
        )

    async def async_turn_on(self) -> None:
        """Activate Eco mode."""
        await self._hub.async_set_pagosa_eco(True)

    async def async_turn_off(self) -> None:
        """Deactivate Eco mode."""
        await self._hub.async_set_pagosa_eco(False)


class PagosaBoostSwitch(PagosaBaseSwitch):
    """Switch for Pagosa Boost mode."""

    def __init__(
        self,
        coordinator: Hub,
        config_title: str,
        config_device_id: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize Boost switch."""
        super().__init__(
            coordinator=coordinator,
            name="Boost ECS",
            icon="mdi:rocket-launch",
            config_title=config_title,
            config_device_id=config_device_id,
            config_uniq_id=config_uniq_id,
            unique_suffix="boost",
        )

    @property
    def is_on(self) -> bool:
        """Return whether Boost is active."""
        operating_mode = self._hub.get_overkiz_state(
            "core:OperatingModeState",
            {},
        )

        if not isinstance(operating_mode, dict):
            return False

        return (
            str(operating_mode.get("relaunch", "off")).lower() == "on"
        )

    async def async_turn_on(self) -> None:
        """Activate Boost without changing its duration."""
        await self._hub.async_set_pagosa_boost(True)

    async def async_turn_off(self) -> None:
        """Deactivate Boost without changing Absence."""
        await self._hub.async_set_pagosa_boost(False)


class PagosaOperatingModeSwitch(PagosaBaseSwitch):
    """Switch for Pagosa Absence mode."""

    def __init__(
        self,
        coordinator: Hub,
        mode_key: str,
        name: str,
        icon: str,
        config_title: str,
        config_device_id: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize Absence switch."""
        super().__init__(
            coordinator=coordinator,
            name=name,
            icon=icon,
            config_title=config_title,
            config_device_id=config_device_id,
            config_uniq_id=config_uniq_id,
            unique_suffix=mode_key,
        )

        self._mode_key = mode_key

    @property
    def is_on(self) -> bool:
        """Return whether Absence mode is active."""
        operating_mode = self._hub.get_overkiz_state(
            "core:OperatingModeState",
            {},
        )

        if not isinstance(operating_mode, dict):
            return False

        return (
            str(operating_mode.get(self._mode_key, "off")).lower()
            == "on"
        )

    async def async_turn_on(self) -> None:
        """Activate Absence."""
        await self._hub.async_set_pagosa_away(True)

    async def async_turn_off(self) -> None:
        """Deactivate Absence."""
        await self._hub.async_set_pagosa_away(False)


class CozytouchSwitch(SwitchEntity, CozytouchSensor):
    """Class for classic Cozytouch switches."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
    ) -> None:
        """Initialize a Switch entity."""
        capability_id = capability["capabilityId"]
        super().__init__(
            coordinator=coordinator,
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=(
                f"{DOMAIN}_{config_uniq_id}_switch_{str(capability_id)}"
            ),
            name=name,
        )
        self._state = False
        self._attr_device_class = SwitchDeviceClass.SWITCH

        self._value_off = capability.get("value_off", "0")
        self._value_on = capability.get("value_on", "1")

    @property
    def is_on(self) -> bool:
        """Return the state."""
        value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )
        self._state = value is not None and value == self._value_on
        return self._state

    async def async_turn_on(self) -> None:
        """Turn on."""
        await self.coordinator.set_capability_value(
            self._capability["capabilityId"],
            self._value_on,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.coordinator.set_capability_value(
            self._capability["capabilityId"],
            self._value_off,
        )
        await self.coordinator.async_request_refresh()

    async def async_toggle(self) -> None:
        """Toggle the switch."""
        if self.is_on:
            await self.async_turn_off()
        else:
            await self.async_turn_on()


class CozytouchAwayModeSwitch(SwitchEntity, CozytouchSensor):
    """Class for classic Cozytouch away mode switch."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
    ) -> None:
        """Initialize a Switch entity."""
        capability_id = capability["capabilityId"]
        super().__init__(
            coordinator=coordinator,
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=(
                f"{DOMAIN}_{config_uniq_id}_switch_{str(capability_id)}"
            ),
            name=name,
        )
        self._state = False
        self._attr_device_class = SwitchDeviceClass.SWITCH

        self._nb_ignore = 0

        self._value_off = capability.get("value_off", "0")
        self._value_on = capability.get("value_on", "1")
        self._value_pending = capability.get("value_pending", "2")

    @property
    def is_on(self) -> bool:
        """Return the state."""
        if self._nb_ignore > 0:
            self._nb_ignore -= 1
        else:
            value = self.coordinator.get_capability_value(
                self._capability["capabilityId"]
            )
            self._state = value is not None and value != self._value_off

        return self._state

    async def async_turn_on(self) -> None:
        """Turn on."""
        timestamp_start = self.coordinator.get_away_mode_start()
        timestamp_end = self.coordinator.get_away_mode_end()

        if (
            timestamp_start is None
            or timestamp_end is None
            or timestamp_start == 0
            or timestamp_end == 0
            or timestamp_start > timestamp_end
        ):
            timestamp_start = (
                datetime.now(tz=dt_util.DEFAULT_TIME_ZONE).timestamp() + 60
            )
            timestamp_end = timestamp_start + (2 * 24 * 60 * 60)

        self._nb_ignore = 5
        self._state = True

        await self.coordinator.set_away_mode_timestamps(
            self._capability["capabilityId"],
            self._value_pending,
            self._capability["timestampsCapabilityId"],
            int(timestamp_start),
            int(timestamp_end),
        )

        self._nb_ignore = 1
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off."""
        self._nb_ignore = 5
        self._state = False

        await self.coordinator.set_away_mode_timestamps(
            self._capability["capabilityId"],
            self._value_off,
            self._capability["timestampsCapabilityId"],
            None,
            None,
        )

        self._nb_ignore = 1
        await self.coordinator.async_request_refresh()

    async def async_toggle(self) -> None:
        """Toggle the away mode switch."""
        if self._state:
            await self.async_turn_off()
        else:
            await self.async_turn_on()