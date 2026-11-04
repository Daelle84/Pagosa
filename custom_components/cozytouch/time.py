
"""Time entities for Atlantic Cozytouch and Sauter Pagosa."""

from __future__ import annotations

from datetime import time as dt_time
import logging

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
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
    """Set up time entities."""
    try:
        hub = hass.data[DOMAIN][config_entry.entry_id]
    except KeyError:
        _LOGGER.error(
            "%s: cannot initialize times: hub not found",
            config_entry.title,
        )
        return

    times = []

    if hub.is_overkiz():
        device = hub.get_overkiz_device()

        if not device:
            _LOGGER.warning("Pagosa Overkiz device not found")
            return

        slots = hub.get_overkiz_state("io:ProgrammingSlotsState")

        if isinstance(slots, dict):
            for slot_key in ("slot1", "slot2"):
                slot = slots.get(slot_key)

                if not isinstance(slot, dict):
                    continue

                for boundary in ("start", "end"):
                    times.append(
                        PagosaProgrammingTime(
                            coordinator=hub,
                            slot_key=slot_key,
                            boundary=boundary,
                            config_title=config_entry.title,
                            config_uniq_id=config_entry.entry_id,
                        )
                    )
    else:
        capabilities = hub.get_capabilities_for_device()

        for capability in capabilities:
            if capability["type"] == "time_adjustment":
                times.append(
                    CozytouchTime(
                        coordinator=hub,
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                    )
                )

    if times:
        async_add_entities(times, True)


class PagosaProgrammingTime(CoordinatorEntity[Hub], TimeEntity):
    """Time entity for a Pagosa programming slot."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: Hub,
        slot_key: str,
        boundary: str,
        config_title: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize a programming time entity."""
        super().__init__(coordinator)

        self._hub = coordinator
        self._slot_key = slot_key
        self._boundary = boundary

        slot_number = slot_key[-1]
        boundary_name = "Début" if boundary == "start" else "Fin"

        self._attr_name = f"Programmation {slot_number} - {boundary_name}"
        self._attr_unique_id = (
            f"{config_uniq_id}_pagosa_{slot_key}_{boundary}"
        )

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
    def native_value(self) -> dt_time | None:
        """Return the configured time."""
        slots = self._hub.get_overkiz_state("io:ProgrammingSlotsState")

        if not isinstance(slots, dict):
            return None

        slot = slots.get(self._slot_key)

        if not isinstance(slot, dict):
            return None

        value = slot.get(self._boundary)

        if not isinstance(value, str):
            return None

        try:
            hour, minute = value.split(":", 1)
            return dt_time(int(hour), int(minute))
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Invalid Pagosa programming time: %s",
                value,
            )
            return None

    async def async_set_value(self, value: dt_time) -> None:
        """Update one boundary of a programming slot."""
        slots = self._hub.get_overkiz_state("io:ProgrammingSlotsState")

        if not isinstance(slots, dict):
            raise RuntimeError("Pagosa programming slots are unavailable")

        updated_slots = {
            key: dict(slot) if isinstance(slot, dict) else slot
            for key, slot in slots.items()
        }

        if self._slot_key not in updated_slots:
            updated_slots[self._slot_key] = {
                "start": "00:00",
                "end": "00:00",
            }

        updated_slots[self._slot_key][self._boundary] = (
            f"{value.hour:02d}:{value.minute:02d}"
        )

        await self._hub.async_execute_overkiz_command(
            "setProgrammingSlots",
            [updated_slots],
            label=f"Pagosa programmation {self._slot_key}",
            refresh=False,
        )

        await self._hub._refresh_overkiz_setup()
        await self._hub.async_request_refresh()


class CozytouchTime(TimeEntity, CozytouchSensor):
    """Classic Atlantic Cozytouch time entity."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a Time entity."""
        super().__init__(
            coordinator=coordinator,
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            name=name,
            icon=icon,
        )

    async def async_set_value(self, value: dt_time) -> None:
        """Update the current value."""
        minutes = (value.hour * 60) + value.minute

        await self.coordinator.set_capability_value(
            self._capability["capabilityId"],
            str(minutes),
        )

    @property
    def native_value(self) -> dt_time | None:
        """Retrieve value from hub."""
        raw_value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )

        if raw_value is None:
            return None

        try:
            value = int(raw_value)
            hours, minutes = divmod(value, 60)
            return dt_time(hours, minutes)
        except (ValueError, TypeError):
            return None
