
"""Date/Time entities for Atlantic Cozytouch and Sauter Pagosa."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CozytouchCapabilityVariableType
from .hub import Hub
from .sensor import CozytouchSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up datetime entities."""
    try:
        hub = hass.data[DOMAIN][config_entry.entry_id]
    except KeyError:
        _LOGGER.error(
            "%s: cannot initialize datetimes: hub not found",
            config_entry.title,
        )
        return

    datetimes = []

    if hub.is_overkiz():
        device = hub.get_overkiz_device()

        if device and hub.get_overkiz_state("core:DateTimeState") is not None:
            datetimes.append(
                PagosaDateTime(
                    coordinator=hub,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                )
            )
    else:
        capabilities = hub.get_capabilities_for_device()

        for capability in capabilities:
            if capability["type"] == "away_mode_timestamps":
                datetimes.append(
                    CozytouchAwayModeDateTime(
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                        attr_uniq_id=config_entry.entry_id + "_0",
                        coordinator=hub,
                        name=capability["name_0"],
                        icon=capability.get("icon_0"),
                        separator=",",
                        timestamp_index=0,
                    )
                )
                datetimes.append(
                    CozytouchAwayModeDateTime(
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                        attr_uniq_id=config_entry.entry_id + "_1",
                        coordinator=hub,
                        name=capability["name_1"],
                        icon=capability.get("icon_1"),
                        separator=",",
                        timestamp_index=1,
                    )
                )

    if datetimes:
        async_add_entities(datetimes, True)


class PagosaDateTime(CoordinatorEntity[Hub], DateTimeEntity):
    """Date and time entity for Pagosa."""

    _attr_has_entity_name = True
    _attr_name = "Date et heure de l'appareil"
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: Hub,
        config_title: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize Pagosa datetime entity."""
        super().__init__(coordinator)

        self._hub = coordinator
        self._attr_unique_id = f"{config_uniq_id}_pagosa_datetime"

        device = coordinator.get_overkiz_device() or {}

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, str(device.get("deviceURL", config_uniq_id)))
            },
            name=device.get("label") or config_title or "Sauter Pagosa 270L",
            manufacturer="Sauter",
            model="Pagosa 270L",
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return (
            self._hub.online
            and self._hub.last_update_success
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the Pagosa date and time."""
        value = self._hub.get_overkiz_state("core:DateTimeState")

        if not isinstance(value, dict):
            return None

        try:
            return datetime(
                year=int(value["year"]),
                month=int(value["month"]),
                day=int(value["day"]),
                hour=int(value["hour"]),
                minute=int(value["minute"]),
                second=int(value.get("second", 0)),
                tzinfo=dt_util.DEFAULT_TIME_ZONE,
            )
        except (KeyError, TypeError, ValueError):
            _LOGGER.warning("Invalid Pagosa DateTimeState: %s", value)
            return None

    async def async_set_value(self, value: datetime) -> None:
        """Set the Pagosa date and time."""
        local_value = dt_util.as_local(value)

        parameters = {
            "year": local_value.year,
            "month": local_value.month,
            "day": local_value.day,
            "weekday": local_value.weekday(),
            "hour": local_value.hour,
            "minute": local_value.minute,
            "second": local_value.second,
        }

        await self._hub.async_execute_overkiz_command(
            "setDateTime",
            [parameters],
            label="Pagosa réglage date et heure",
            refresh=False,
        )

        await self._hub._refresh_overkiz_setup()
        await self._hub.async_request_refresh()


class CozytouchDateTime(DateTimeEntity, CozytouchSensor):
    """Classic Cozytouch datetime entity."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
        separator: str | None = None,
        timestamp_index: int | None = None,
        attr_uniq_id: str | None = None,
    ) -> None:
        """Initialize a datetime entity."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=attr_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
            value_type=CozytouchCapabilityVariableType.STRING,
        )
        self._separator = separator
        self._timestamp_index = timestamp_index

    async def async_set_value(self, value: datetime) -> None:
        """Update the current value."""
        old_value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )

        if old_value is not None:
            old_value = old_value.translate(str.maketrans("", "", "[]"))
            old_timestamps = old_value.split(self._separator, 2)

            if self._timestamp_index < len(old_timestamps):
                old_timestamps[self._timestamp_index] = str(
                    int(value.timestamp())
                )

                new_value = "[" + ",".join(old_timestamps) + "]"

                await self.coordinator.set_capability_value(
                    self._capability["capabilityId"],
                    new_value,
                )

    @property
    def native_value(self) -> datetime | None:
        """Retrieve value from hub."""
        value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )

        if value is not None:
            try:
                value = value.translate(str.maketrans("", "", "[]"))
                timestamps = value.split(self._separator, 2)

                if self._timestamp_index < len(timestamps):
                    timestamp = int(timestamps[self._timestamp_index])

                    if timestamp > 0:
                        return datetime.fromtimestamp(
                            timestamp,
                            tz=dt_util.DEFAULT_TIME_ZONE,
                        )
            except (ValueError, TypeError, AttributeError):
                _LOGGER.warning("Invalid Cozytouch datetime value: %s", value)

        return None


class CozytouchAwayModeDateTime(DateTimeEntity, CozytouchSensor):
    """Classic Cozytouch away mode datetime entity."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
        separator: str | None = None,
        timestamp_index: int | None = None,
        attr_uniq_id: str | None = None,
    ) -> None:
        """Initialize a datetime entity."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=attr_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
            value_type=CozytouchCapabilityVariableType.STRING,
        )
        self._separator = separator
        self._timestamp_index = timestamp_index

    async def async_set_value(self, value: datetime) -> None:
        """Update the current value."""
        timestamp = value.timestamp()

        if self._timestamp_index == 0:
            await self.coordinator.set_away_mode_start(
                self._capability["capabilityId"],
                int(timestamp),
            )
        elif self._timestamp_index == 1:
            await self.coordinator.set_away_mode_end(
                self._capability["capabilityId"],
                int(timestamp),
            )

    @property
    def native_value(self) -> datetime | None:
        """Retrieve value from hub."""
        value = None

        if self._timestamp_index == 0:
            value = self.coordinator.get_away_mode_start()
        elif self._timestamp_index == 1:
            value = self.coordinator.get_away_mode_end()

        if value is not None and value > 0:
            return datetime.fromtimestamp(
                value,
                tz=dt_util.DEFAULT_TIME_ZONE,
            )

        return None
