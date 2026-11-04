"""The Atlantic Cozytouch integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from . import hub
from .const import CONF_DUMPJSON, DOMAIN

_LOGGER = logging.getLogger(__name__)

try:
    from . import pagosa_absence  # noqa: F401
    from . import pagosa_controls  # noqa: F401
    from . import pagosa_select  # noqa: F401
    from . import pagosa_sensor  # noqa: F401
except Exception:  # noqa: BLE001
    _LOGGER.exception("Unable to load the Pagosa fixes")

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.CLIMATE,
    Platform.DATETIME,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Optional(CONF_DUMPJSON): cv.boolean})},
    extra=vol.ALLOW_EXTRA,
)

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Atlantic Cozytouch from a config entry."""
    the_hub = hub.Hub(
        hass,
        entry.data["username"],
        entry.data["password"],
        entry.data["deviceId"],
    )

    if "dump_json" in entry.data:
        the_hub.set_dump_json(entry.data["dump_json"])

    await the_hub.connect()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = the_hub

    the_hub.set_create_entities_for_unknown_entities(
        entry.data["create_unknown"]
    )
    await the_hub.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unload_ok:
        the_hub = hass.data[DOMAIN].pop(entry.entry_id)
        if hasattr(the_hub, "async_close"):
            await the_hub.async_close()

    return unload_ok
