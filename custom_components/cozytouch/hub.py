"""Atlantic Cozytouch Hub with Overkiz support for Sauter Pagosa."""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import json
import logging
import time

from aiohttp import ClientSession, ContentTypeError, FormData

from homeassistant import exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .capability import get_capability_infos
from .const import COZYTOUCH_ATLANTIC_API, COZYTOUCH_CLIENT_ID
from .model import get_model_infos

_LOGGER = logging.getLogger(__name__)

OVERKIZ_HOST = "https://ha110-1.overkiz.com"
OVERKIZ_API = "/enduser-mobile-web/enduserAPI"

PAGOSA_CONTROLLABLE_NAME = (
    "io:AtlanticDomesticHotWaterProductionV3IOComponent"
)
PAGOSA_ENERGY_CONTROLLABLE_NAME = (
    "io:DHWCumulatedElectricalEnergyConsumptionIOSystemDeviceSensor"
)

OVERKIZ_UPDATE_INTERVAL = 300
OVERKIZ_MIN_REFRESH_INTERVAL = 30
OVERKIZ_DEFAULT_RETRY_DELAY = 300


class Hub(DataUpdateCoordinator):
    """Atlantic Cozytouch Hub."""

    manufacturer = "Atlantic Group"
    _localization = {}
    _setup = {}
    _zones = {}

    _timestamp_away_mode_last_change = None
    _timestamp_away_mode_start = None
    _timestamp_away_mode_end = None

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        deviceId: int | str | None = None,
    ) -> None:
        """Initialize hub."""
        super().__init__(
            hass,
            _LOGGER,
            name="Cozytouch_" + str(deviceId),
            update_interval=timedelta(seconds=OVERKIZ_UPDATE_INTERVAL),
        )

        self._session = ClientSession()
        self._host = "none"
        self._hass = hass
        self._username = username
        self._password = password
        self._deviceId = deviceId
        self._zoneId = -1
        self._access_token = ""
        self._id = "cozytouch." + username.lower()
        self._create_unknown = False
        self._dump_json = False
        self._devices = []

        self._overkiz_host = OVERKIZ_HOST
        self._overkiz_jwt = None
        self._overkiz_setup = None
        self._overkiz_devices = []
        self._overkiz_device = None
        self._overkiz_energy_device = None
        self._overkiz_states = {}
        self._overkiz_energy_states = {}
        self._overkiz_gateway = None
        self._is_overkiz = False

        self._overkiz_last_setup_refresh = 0.0
        self._overkiz_retry_after = 0.0
        self._overkiz_refresh_lock = asyncio.Lock()
        self._overkiz_auth_lock = asyncio.Lock()

        # Pagosa operations are serialized as complete transactions.
        self._pagosa_command_lock = asyncio.Lock()
        self._pagosa_optimistic_states = {}

        self.online = False

        model_infos = self.get_model_infos()
        if "name" in model_infos:
            self.device_info = DeviceInfo(
                entry_type=DeviceEntryType.SERVICE,
                identifiers={("cozytouch", "cozytouch" + str(deviceId))},
                manufacturer="Atlantic",
                name=model_infos["name"],
            )

        self._timestamps_away_mode_capability_id = None

        self._test_load = False
        if self._test_load:
            self._dump_json = False
            self.online = True
            with open(
                self._hass.config.config_dir + "/cozytouch_eoras2.json",
                encoding="utf-8",
            ) as json_file:
                file_contents = json_file.read()
                self.update_devices_from_json_data(json.loads(file_contents))

    @property
    def hub_id(self) -> str:
        """Return hub ID."""
        return self._id

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def _authenticate_atlantic(self) -> bool:
        """Obtain a fresh Atlantic access token."""
        try:
            async with self._session.post(
                COZYTOUCH_ATLANTIC_API + "/users/token",
                data=FormData(
                    {
                        "grant_type": "password",
                        "scope": "openid",
                        "username": "GA-PRIVATEPERSON/" + self._username,
                        "password": self._password,
                    }
                ),
                headers={
                    "Authorization": f"Basic {COZYTOUCH_CLIENT_ID}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            ) as response:
                token = await response.json(content_type=None)

                if response.status != 200:
                    _LOGGER.error(
                        "Atlantic authentication failed: HTTP %s",
                        response.status,
                    )
                    return False

                if (
                    not isinstance(token, dict)
                    or token.get("error") == "invalid_grant"
                    or "access_token" not in token
                ):
                    _LOGGER.error("Atlantic did not return a valid access token")
                    return False

                self._access_token = token["access_token"]
                return True

        except Exception:
            _LOGGER.exception("Unable to authenticate with Atlantic")
            return False

    async def _login_overkiz(self) -> bool:
        """Obtain a fresh Overkiz JWT and establish a new Overkiz session."""
        async with self._overkiz_auth_lock:
            if not await self._authenticate_atlantic():
                self.online = False
                return False

            try:
                async with self._session.get(
                    COZYTOUCH_ATLANTIC_API + "/magellan/accounts/jwt",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json",
                    },
                ) as response:
                    if response.status == 429:
                        self._record_overkiz_rate_limit(response, "JWT")
                        return False

                    if response.status != 200:
                        _LOGGER.error(
                            "Overkiz JWT request failed: HTTP %s",
                            response.status,
                        )
                        return False

                    jwt_data = await response.json(content_type=None)

                if isinstance(jwt_data, dict):
                    jwt = (
                        jwt_data.get("jwt")
                        or jwt_data.get("token")
                        or jwt_data.get("access_token")
                    )
                elif isinstance(jwt_data, str):
                    jwt = jwt_data
                else:
                    jwt = None

                if not jwt:
                    _LOGGER.error("Atlantic did not return an Overkiz JWT")
                    return False

                async with self._session.post(
                    self._overkiz_host + OVERKIZ_API + "/login",
                    data={"jwt": jwt},
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                ) as response:
                    if response.status == 429:
                        self._record_overkiz_rate_limit(response, "login")
                        return False

                    login_data = await response.json(content_type=None)

                    if response.status != 200 or not login_data.get("success"):
                        _LOGGER.error(
                            "Overkiz login failed: HTTP %s",
                            response.status,
                        )
                        return False

                self._overkiz_jwt = jwt
                _LOGGER.info("Overkiz authentication renewed successfully")
                return True

            except Exception:
                _LOGGER.exception("Unable to renew Overkiz authentication")
                return False

    async def test_connection(self) -> bool:
        """Test connection."""
        await self.connect()
        return self.online

    async def connect(self) -> bool:
        """Connect to Cozytouch or Overkiz."""
        if self.online:
            return True

        try:
            if not await self._authenticate_atlantic():
                raise CannotConnect

            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }

            async with self._session.get(
                COZYTOUCH_ATLANTIC_API + "/magellan/cozytouch/setupviewv2",
                headers=headers,
            ) as response:
                if response.status != 200:
                    _LOGGER.warning(
                        "Atlantic setup unavailable (HTTP %s); trying Overkiz",
                        response.status,
                    )
                    return await self._connect_overkiz()

                json_data = await response.json(content_type=None)

            if not isinstance(json_data, list) or not json_data:
                _LOGGER.warning("Atlantic setup is empty; trying Overkiz")
                return await self._connect_overkiz()

            setup = json_data[0]

            for key in (
                "absence",
                "address",
                "area",
                "currency",
                "id",
                "mainDHWEnergy",
                "mainHeatingEnergy",
                "name",
                "numberOfPersons",
                "numberOfRooms",
                "setupBuildingDate",
                "type",
            ):
                if key in setup:
                    self._setup[key] = copy.deepcopy(setup[key])

            await asyncio.get_running_loop().run_in_executor(
                None, self.update_devices_from_json_data, json_data
            )

            if "address" in setup:
                await self._update_localization(
                    setup["address"].get("country")
                )

            if "zones" in setup:
                self._zones = copy.deepcopy(setup["zones"])

            if not self._devices:
                _LOGGER.info("No Atlantic devices found; trying Overkiz")
                return await self._connect_overkiz()

            self.online = True
            self._is_overkiz = False

        except CannotConnect:
            self.online = False
            _LOGGER.error("Unable to connect to Atlantic Cozytouch")
        except (ContentTypeError, ValueError, KeyError):
            self.online = False
            _LOGGER.exception("Invalid Atlantic API response")

        return self.online

    async def _connect_overkiz(self) -> bool:
        """Connect to Overkiz using a fresh Atlantic JWT."""
        try:
            if not await self._login_overkiz():
                return False

            async with self._session.get(
                self._overkiz_host + OVERKIZ_API + "/setup",
            ) as response:
                if response.status == 429:
                    self._record_overkiz_rate_limit(response, "initial setup")
                    return False

                if response.status != 200:
                    _LOGGER.error(
                        "Overkiz setup failed: HTTP %s",
                        response.status,
                    )
                    return False

                setup_data = await response.json(content_type=None)

            self._apply_overkiz_setup(setup_data)

            if self._overkiz_device is None:
                _LOGGER.error("Pagosa water heater not found in Overkiz setup")
                return False

            self._is_overkiz = True
            self._deviceId = self._overkiz_device.get("deviceURL")
            self._overkiz_last_setup_refresh = time.monotonic()
            self._overkiz_retry_after = 0.0
            self.online = True

            _LOGGER.info(
                "Overkiz connected. Pagosa found: %s (%s). Energy device: %s",
                self._overkiz_device.get("label")
                or self._overkiz_device.get("deviceName"),
                self._deviceId,
                (
                    self._overkiz_energy_device.get("deviceURL")
                    if self._overkiz_energy_device
                    else "not found"
                ),
            )

            if self._overkiz_energy_device is None:
                _LOGGER.warning(
                    "Pagosa energy sensor device was not found in setup"
                )

            return True

        except Exception:
            _LOGGER.exception("Unable to connect to Overkiz")
            self.online = False
            return False

    # ------------------------------------------------------------------
    # Overkiz setup and state handling
    # ------------------------------------------------------------------

    def _apply_overkiz_setup(self, setup_data) -> None:
        """Store setup data and update selected devices and states."""
        self._overkiz_setup = setup_data
        self._overkiz_devices = self._extract_overkiz_devices(setup_data)
        self._overkiz_gateway = (
            setup_data.get("gateway")
            if isinstance(setup_data, dict)
            else None
        )
        self._select_overkiz_devices()
        self._read_overkiz_states_from_setup()

    @staticmethod
    def _extract_overkiz_devices(setup_data) -> list:
        """Extract devices from Overkiz setup response."""
        if isinstance(setup_data, dict):
            devices = setup_data.get("devices", [])
            return devices if isinstance(devices, list) else []

        if isinstance(setup_data, list):
            devices = []
            for item in setup_data:
                if isinstance(item, dict):
                    item_devices = item.get("devices", [])
                    if isinstance(item_devices, list):
                        devices.extend(item_devices)
            return devices

        return []

    def _select_overkiz_devices(self) -> None:
        """Select Pagosa heater and its energy sensor."""
        self._overkiz_device = None
        self._overkiz_energy_device = None

        for device in self._overkiz_devices:
            if not isinstance(device, dict):
                continue

            if device.get("deviceURL") == self._deviceId:
                self._overkiz_device = device

            if device.get("controllableName") == PAGOSA_CONTROLLABLE_NAME:
                self._overkiz_device = device

            if (
                device.get("controllableName")
                == PAGOSA_ENERGY_CONTROLLABLE_NAME
            ):
                self._overkiz_energy_device = device

        if self._overkiz_device is None:
            self._overkiz_device = next(
                (
                    device
                    for device in self._overkiz_devices
                    if isinstance(device, dict)
                    and device.get("controllableName")
                    == PAGOSA_CONTROLLABLE_NAME
                ),
                None,
            )

        if self._overkiz_energy_device is None and self._overkiz_device:
            heater_url = self._overkiz_device.get("deviceURL", "")
            base_url = heater_url.split("#", 1)[0]
            self._overkiz_energy_device = next(
                (
                    device
                    for device in self._overkiz_devices
                    if isinstance(device, dict)
                    and device.get("deviceURL", "").startswith(base_url + "#")
                    and device.get("controllableName")
                    == PAGOSA_ENERGY_CONTROLLABLE_NAME
                ),
                None,
            )

    def _read_overkiz_states_from_setup(self) -> None:
        """Read heater and energy states from setup response."""
        self._overkiz_states = {}
        self._overkiz_energy_states = {}

        if self._overkiz_device:
            for state in self._overkiz_device.get("states", []):
                if isinstance(state, dict) and "name" in state:
                    self._overkiz_states[state["name"]] = state.get("value")

        if self._overkiz_energy_device:
            for state in self._overkiz_energy_device.get("states", []):
                if isinstance(state, dict) and "name" in state:
                    self._overkiz_energy_states[state["name"]] = (
                        state.get("value")
                    )

    @staticmethod
    def _get_retry_delay(response) -> int:
        """Get retry delay from Retry-After header."""
        retry_after = response.headers.get("Retry-After")

        if retry_after:
            try:
                return max(1, int(retry_after))
            except ValueError:
                try:
                    retry_date = parsedate_to_datetime(retry_after)
                    now = datetime.now(retry_date.tzinfo)
                    return max(1, int((retry_date - now).total_seconds()))
                except (TypeError, ValueError, OverflowError):
                    pass

        return OVERKIZ_DEFAULT_RETRY_DELAY

    def _record_overkiz_rate_limit(self, response, context: str) -> int:
        """Record the server's rate-limit delay."""
        delay = self._get_retry_delay(response)
        self._overkiz_retry_after = max(
            self._overkiz_retry_after,
            time.monotonic() + delay,
        )
        _LOGGER.warning(
            "Overkiz rate limit reached during %s (HTTP 429). "
            "Next request allowed in %s seconds",
            context,
            delay,
        )
        return delay

    def _overkiz_rate_limit_remaining(self) -> int:
        """Return remaining rate-limit delay in seconds."""
        return max(0, int(self._overkiz_retry_after - time.monotonic()))

    async def _refresh_overkiz_setup(
        self,
        force: bool = False,
    ) -> bool:
        """Refresh Overkiz setup with rate limiting and 401 recovery."""
        if not self._is_overkiz:
            return False

        async with self._overkiz_refresh_lock:
            remaining = self._overkiz_rate_limit_remaining()
            if remaining:
                _LOGGER.debug(
                    "Overkiz refresh postponed for %s seconds",
                    remaining,
                )
                return False

            elapsed = time.monotonic() - self._overkiz_last_setup_refresh
            if not force and elapsed < OVERKIZ_MIN_REFRESH_INTERVAL:
                _LOGGER.debug(
                    "Overkiz refresh skipped (last refresh %.1f seconds ago)",
                    elapsed,
                )
                return False

            for attempt in range(2):
                try:
                    async with self._session.get(
                        self._overkiz_host + OVERKIZ_API + "/setup",
                    ) as response:
                        if response.status == 401 and attempt == 0:
                            _LOGGER.warning(
                                "Overkiz session expired during setup refresh; "
                                "reauthenticating"
                            )
                            if not await self._login_overkiz():
                                self.online = False
                                return False
                            continue

                        if response.status == 429:
                            self._record_overkiz_rate_limit(
                                response, "setup refresh"
                            )
                            return False

                        if response.status != 200:
                            _LOGGER.warning(
                                "Overkiz setup refresh failed: HTTP %s",
                                response.status,
                            )
                            return False

                        setup_data = await response.json(content_type=None)

                    self._apply_overkiz_setup(setup_data)

                    if self._overkiz_device is None:
                        _LOGGER.warning(
                            "Pagosa device was not found during Overkiz refresh"
                        )
                        return False

                    self._overkiz_last_setup_refresh = time.monotonic()
                    self.online = True
                    return True

                except Exception:
                    _LOGGER.exception("Unable to refresh Overkiz setup")
                    return False

            return False

    def get_overkiz_state(self, state_name: str, default=None):
        """Return a Pagosa state, including a temporary optimistic state."""
        if state_name in self._pagosa_optimistic_states:
            return self._pagosa_optimistic_states[state_name]

        return self._overkiz_states.get(state_name, default)

    def get_overkiz_device(self):
        """Return the Pagosa heater device."""
        return self._overkiz_device

    def get_overkiz_states(self):
        """Return all Pagosa heater states."""
        return self._overkiz_states.copy()

    def get_overkiz_energy_device(self):
        """Return the Pagosa energy sensor device."""
        return self._overkiz_energy_device

    def get_overkiz_energy_state(self, state_name: str, default=None):
        """Return a Pagosa energy sensor state."""
        return self._overkiz_energy_states.get(state_name, default)

    def get_overkiz_energy_states(self):
        """Return all Pagosa energy sensor states."""
        return self._overkiz_energy_states.copy()

    def is_overkiz(self) -> bool:
        """Return whether the selected device uses Overkiz."""
        return self._is_overkiz

    def get_overkiz_commands(self) -> set[str]:
        """Return command names advertised by Pagosa."""
        if not self._overkiz_device:
            return set()

        commands = self._overkiz_device.get("availableCommands", [])
        result = set()

        for command in commands:
            if isinstance(command, str):
                result.add(command)
            elif isinstance(command, dict) and command.get("name"):
                result.add(command["name"])

        return result

    # ------------------------------------------------------------------
    # Overkiz commands
    # ------------------------------------------------------------------

    async def async_execute_overkiz_command(
        self,
        command: str,
        parameters: list | dict | None = None,
        label: str | None = None,
        refresh: bool = True,
    ) -> None:
        """Execute a Pagosa command, recovering once from HTTP 401."""
        if not self._is_overkiz or not self._overkiz_device:
            raise exceptions.HomeAssistantError(
                "The Pagosa Overkiz device is not connected"
            )

        remaining = self._overkiz_rate_limit_remaining()
        if remaining:
            raise exceptions.HomeAssistantError(
                f"Overkiz rate limit is active. Retry in {remaining} seconds"
            )

        device_url = self._overkiz_device.get("deviceURL")
        if not device_url:
            raise exceptions.HomeAssistantError(
                "The Pagosa device URL is missing"
            )

        available_commands = self.get_overkiz_commands()
        if available_commands and command not in available_commands:
            raise exceptions.HomeAssistantError(
                f"The Pagosa does not advertise the command {command}"
            )

        if parameters is None:
            parameters = []

        payload = {
            "label": label or f"Pagosa: {command}",
            "actions": [
                {
                    "deviceURL": device_url,
                    "commands": [
                        {
                            "name": command,
                            "parameters": parameters,
                        }
                    ],
                }
            ],
        }

        _LOGGER.info(
            "Sending Pagosa command %s with parameters %s",
            command,
            parameters,
        )

        for attempt in range(2):
            remaining = self._overkiz_rate_limit_remaining()
            if remaining:
                raise exceptions.HomeAssistantError(
                    f"Overkiz rate limit is active. Retry in {remaining} seconds"
                )

            try:
                async with self._session.post(
                    self._overkiz_host + OVERKIZ_API + "/exec/apply",
                    json=payload,
                ) as response:
                    response_text = await response.text()

                    if response.status == 401 and attempt == 0:
                        _LOGGER.warning(
                            "Overkiz rejected command %s with HTTP 401. "
                            "Renewing session and retrying once",
                            command,
                        )
                        if not await self._login_overkiz():
                            self.online = False
                            raise exceptions.HomeAssistantError(
                                "Overkiz authentication renewal failed. "
                                "Please check the Cozytouch credentials."
                            )
                        continue

                    if response.status == 429:
                        delay = self._record_overkiz_rate_limit(
                            response, f"command {command}"
                        )
                        raise exceptions.HomeAssistantError(
                            f"Overkiz rate limit reached. Retry in {delay} seconds"
                        )

                    if response.status not in (200, 201, 202):
                        _LOGGER.error(
                            "Pagosa command %s failed: HTTP %s - %s",
                            command,
                            response.status,
                            response_text,
                        )
                        raise exceptions.HomeAssistantError(
                            f"Overkiz rejected command {command} "
                            f"(HTTP {response.status}): {response_text}"
                        )

                    break

            except exceptions.HomeAssistantError:
                raise
            except Exception as err:
                _LOGGER.exception(
                    "Error executing Pagosa command %s", command
                )
                raise exceptions.HomeAssistantError(
                    f"Unable to execute Pagosa command {command}: {err}"
                ) from err
        else:
            raise exceptions.HomeAssistantError(
                f"Overkiz authentication failed for command {command}"
            )

        if refresh:
            refreshed = await self._refresh_overkiz_setup(force=False)
            if refreshed:
                self.async_set_updated_data(self.data)

    # ------------------------------------------------------------------
    # Pagosa transaction handling
    # ------------------------------------------------------------------

    async def async_run_pagosa_operation(
        self,
        operation,
        optimistic_states: dict | None = None,
        label: str = "Pagosa operation",
    ) -> None:
        """Run a serialized Pagosa operation and confirm its state."""
        if self._pagosa_command_lock.locked():
            raise exceptions.HomeAssistantError(
                "Une commande Pagosa est déjà en cours. "
                "Réessaie dans quelques secondes."
            )

        async with self._pagosa_command_lock:
            if optimistic_states:
                self._pagosa_optimistic_states.update(optimistic_states)
                self.async_set_updated_data(self.data)

            try:
                await operation()

                # Allow the appliance to apply the command.
                await asyncio.sleep(3)

                # The lock remains held until the refresh attempt has finished.
                refreshed = await self._refresh_overkiz_setup(force=True)

                if refreshed:
                    _LOGGER.debug(
                        "%s: state confirmed by Overkiz",
                        label,
                    )
                else:
                    _LOGGER.warning(
                        "%s: Overkiz state could not be confirmed. "
                        "The next coordinator refresh will retrieve it.",
                        label,
                    )

            finally:
                self._pagosa_optimistic_states.clear()
                self.async_set_updated_data(self.data)

    async def async_set_pagosa_eco(self, enabled: bool) -> None:
        """Set Eco mode."""
        mode = "manualEcoActive" if enabled else "manualEcoInactive"

        async def operation():
            await self.async_execute_overkiz_command(
                "setDHWMode",
                [mode],
                label="Pagosa Eco",
                refresh=False,
            )
            await self.async_execute_overkiz_command(
                "refreshDHWMode",
                refresh=False,
            )
            await self.async_execute_overkiz_command(
                "refreshTargetTemperature",
                refresh=False,
            )

        await self.async_run_pagosa_operation(
            operation,
            {"io:DHWModeState": mode},
            "Pagosa Eco",
        )

    async def async_set_pagosa_boost(self, enabled: bool) -> None:
        """Set Boost without changing its configured duration."""
        current = self._get_current_operating_mode()
        current["relaunch"] = "on" if enabled else "off"

        async def operation():
            await self._set_operating_mode_flag(
                "relaunch",
                "on" if enabled else "off",
            )
            await self.async_execute_overkiz_command(
                "refreshBoostModeDuration",
                refresh=False,
            )

        await self.async_run_pagosa_operation(
            operation,
            {"core:OperatingModeState": current},
            "Pagosa Boost",
        )

    async def async_set_pagosa_away(self, enabled: bool) -> None:
        """Set Absence using the existing command format."""
        current = self._get_current_operating_mode()
        current["absence"] = "on" if enabled else "off"

        async def operation():
            await self._set_operating_mode_flag(
                "absence",
                "on" if enabled else "off",
            )
            await self.async_execute_overkiz_command(
                "refreshAwayModeDuration",
                refresh=False,
            )

        await self.async_run_pagosa_operation(
            operation,
            {"core:OperatingModeState": current},
            "Pagosa Absence",
        )

    async def set_overkiz_target_temperature(self, value: float) -> None:
        """Set Pagosa target temperature."""
        target = float(value)

        async def operation():
            await self.async_execute_overkiz_command(
                "setTargetTemperature",
                [target],
                label="Set Pagosa target temperature",
                refresh=False,
            )
            await self.async_execute_overkiz_command(
                "refreshTargetTemperature",
                refresh=False,
            )

        await self.async_run_pagosa_operation(
            operation,
            {"core:TargetTemperatureState": target},
            "Pagosa target temperature",
        )

    def _get_current_operating_mode(self) -> dict:
        """Return current operating mode without losing either flag."""
        current = self.get_overkiz_state(
            "core:OperatingModeState",
            {},
        )
        if not isinstance(current, dict):
            current = {}

        return {
            "relaunch": str(current.get("relaunch", "off")).lower(),
            "absence": str(current.get("absence", "off")).lower(),
        }

    async def _set_operating_mode_flag(
        self,
        flag: str,
        value: str,
    ) -> None:
        """Change one operating mode flag while preserving the other."""
        if flag not in ("relaunch", "absence"):
            raise exceptions.HomeAssistantError(
                f"Unsupported operating mode flag: {flag}"
            )

        operating_mode = self._get_current_operating_mode()
        operating_mode[flag] = value

        await self.async_execute_overkiz_command(
            "setCurrentOperatingMode",
            [operating_mode],
            refresh=False,
        )

    async def set_overkiz_boost_duration(self, value: int) -> None:
        """Set Boost duration only when a positive duration is requested."""
        value = int(value)

        if not 0 <= value <= 7:
            raise exceptions.HomeAssistantError(
                "Boost duration must be between 0 and 7 days"
            )

        # Zero means no change: do not alter the duration or Boost state.
        if value == 0:
            return

        async def operation():
            await self.async_execute_overkiz_command(
                "setBoostModeDuration",
                [value],
                label="Set Pagosa Boost duration",
                refresh=False,
            )
            await asyncio.sleep(1)
            await self._set_operating_mode_flag("relaunch", "on")
            await self.async_execute_overkiz_command(
                "refreshBoostModeDuration",
                refresh=False,
            )

        await self.async_run_pagosa_operation(
            operation,
            None,
            "Pagosa Boost duration",
        )

    async def set_overkiz_away_duration(self, value: int) -> None:
        """Set Absence duration using the existing command sequence."""
        value = int(value)

        if not 0 <= value <= 6:
            raise exceptions.HomeAssistantError(
                "Away duration must be between 0 and 6 days"
            )

        async def operation():
            await self.async_execute_overkiz_command(
                "setAwayModeDuration",
                [value],
                label="Set Pagosa Absence duration",
                refresh=False,
            )

            # This is the existing Absence activation command format.
            # Its payload still needs validation against a successful
            # Overkiz request before Absence can be considered fixed.
            await self._set_operating_mode_flag(
                "absence",
                "on" if value > 0 else "off",
            )

            await self.async_execute_overkiz_command(
                "refreshAwayModeDuration",
                refresh=False,
            )

        await self.async_run_pagosa_operation(
            operation,
            None,
            "Pagosa Absence duration",
        )

    # ------------------------------------------------------------------
    # Session handling
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close session."""
        if not self._session.closed:
            await self._session.close()

    async def async_close(self) -> None:
        """Close session from Home Assistant."""
        await self.close()

    # ------------------------------------------------------------------
    # Atlantic device handling
    # ------------------------------------------------------------------

    def update_devices_from_json_data(self, json_data) -> None:
        """Update Atlantic devices list."""
        if self._dump_json:
            with open(
                self._hass.config.config_dir + "/Cozytouch.json",
                "w",
                encoding="utf-8",
            ) as outfile:
                outfile.write(json.dumps(json_data, indent=4))

        if not json_data or not isinstance(json_data, list):
            return

        if len(self._zones) == 0 and "zones" in json_data[0]:
            self._zones = copy.deepcopy(json_data[0]["zones"])

        remote_devices = json_data[0].get("devices", [])

        for local_device in self._devices[:]:
            still_exists = any(
                remote_device["deviceId"] == local_device["deviceId"]
                for remote_device in remote_devices
            )
            if not still_exists:
                self._devices.remove(local_device)

        for remote_device in remote_devices:
            device_index = next(
                (
                    i
                    for i, local_device in enumerate(self._devices)
                    if remote_device["deviceId"] == local_device["deviceId"]
                ),
                -1,
            )

            if device_index == -1:
                device = {
                    "deviceId": remote_device["deviceId"],
                    "name": remote_device["name"],
                    "gatewaySerialNumber": remote_device["gatewaySerialNumber"],
                    "modelId": remote_device["modelId"],
                    "productId": remote_device["productId"],
                    "zoneId": remote_device["zoneId"],
                    "modelInfos": get_model_infos(remote_device["modelId"]),
                    "capabilities": [],
                    "tags": [],
                }

                if "tags" in remote_device:
                    device["tags"] = copy.deepcopy(remote_device["tags"])

                self._devices.append(device)
                device_index = len(self._devices) - 1

            self._zoneId = remote_device.get("zoneId", self._zoneId)

            if self._deviceId == remote_device["deviceId"]:
                self._devices[device_index]["capabilities"] = copy.deepcopy(
                    remote_device.get("capabilities", [])
                )

    def set_create_entities_for_unknown_entities(
        self, create_unknown: bool
    ) -> None:
        """Set option to create entities for unknown capabilities."""
        self._create_unknown = create_unknown

    def get_create_entities_for_unknown_entities(self) -> bool:
        """Get option to create entities for unknown capabilities."""
        return self._create_unknown

    def set_dump_json(self, dump_json: bool) -> None:
        """Set option to dump JSON from API."""
        self._dump_json = dump_json

    async def _async_update_data(self):
        """Refresh data."""
        _LOGGER.debug("_async_update_data %s", self._deviceId)

        if self._test_load:
            return

        if self.online:
            if self._is_overkiz:
                refreshed = await self._refresh_overkiz_setup()
                if refreshed:
                    return self.data
                return self.data

            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }

            async with self._session.get(
                COZYTOUCH_ATLANTIC_API
                + "/magellan/capabilities/?deviceId="
                + str(self._deviceId),
                headers=headers,
            ) as response:
                try:
                    json_data = await response.json()

                    if isinstance(json_data, list):
                        for dev in self._devices:
                            if dev["deviceId"] == self._deviceId:
                                dev["capabilities"] = copy.deepcopy(json_data)
                                break

                        if (
                            self._timestamp_away_mode_last_change is not None
                            and self._timestamps_away_mode_capability_id is not None
                            and self._timestamp_away_mode_start is not None
                            and self._timestamp_away_mode_end is not None
                        ):
                            now = datetime.now(
                                tz=dt_util.DEFAULT_TIME_ZONE
                            ).timestamp()

                            if now - self._timestamp_away_mode_last_change > 20:
                                await self.set_away_mode_timestamps(
                                    None,
                                    None,
                                    self._timestamps_away_mode_capability_id,
                                    self._timestamp_away_mode_start,
                                    self._timestamp_away_mode_end,
                                )
                    else:
                        self.online = False

                except ContentTypeError:
                    self.online = False
        else:
            await self.connect()

        return self.data

    def devices(self):
        """Get available devices."""
        devs = []

        for dev in self._devices:
            devs.append(
                {
                    "deviceId": dev["deviceId"],
                    "name": dev["name"],
                    "model": dev["modelInfos"]["name"],
                }
            )

        for dev in self._overkiz_devices:
            if dev.get("controllableName") == PAGOSA_CONTROLLABLE_NAME:
                devs.append(
                    {
                        "deviceId": dev["deviceURL"],
                        "name": dev.get("label")
                        or dev.get("deviceName")
                        or "Sauter Pagosa",
                        "model": "Sauter Pagosa 270L",
                    }
                )

        return devs

    def get_zone_name(self, zoneId: int | None = None) -> str:
        """Get zone information."""
        if zoneId is None:
            zoneId = self._zoneId

        for zone in self._zones:
            if "id" in zone and zone["id"] == zoneId:
                return zone["name"]

        return str(zoneId)

    def get_model_infos(self, deviceId: int | str | None = None):
        """Get model information."""
        if deviceId is None:
            deviceId = self._deviceId

        for dev in self._overkiz_devices:
            if dev.get("deviceURL") == deviceId:
                return {
                    "name": "Sauter Pagosa 270L",
                    "manufacturer": "Sauter",
                    "model": "Pagosa 270L",
                }

        for dev in self._devices:
            if dev["deviceId"] == deviceId:
                zone_id = dev["zoneId"]

                for master_dev in self._devices:
                    if "tags" in master_dev:
                        for tag in master_dev["tags"]:
                            if (
                                tag.get("label") == "iothubChildrenIds"
                                and tag.get("value") == dev["name"]
                            ):
                                zone_id = master_dev["zoneId"]
                                break

                return get_model_infos(
                    dev["modelId"],
                    self.get_zone_name(zone_id),
                )

        return get_model_infos(-1)

    def get_serial_number(self, deviceId: int | str | None = None) -> str:
        """Get serial number."""
        if deviceId is None:
            deviceId = self._deviceId

        for dev in self._overkiz_devices:
            if dev.get("deviceURL") == deviceId:
                gateway = dev.get("gateway", {})
                if isinstance(gateway, dict):
                    return gateway.get("serialNumber", "Unknown")
                return "Unknown"

        for dev in self._devices:
            if dev["deviceId"] == deviceId:
                return dev["gatewaySerialNumber"]

        return "Unknown"

    def get_capabilities_for_device(self, deviceId: int | str | None = None):
        """Get capabilities for an Atlantic device."""
        if deviceId is None:
            deviceId = self._deviceId

        capabilities = []

        if self._is_overkiz:
            return capabilities

        for dev in self._devices:
            if dev["deviceId"] == deviceId:
                model_infos = get_model_infos(dev["modelId"])

                for capability in dev["capabilities"]:
                    capability_infos = get_capability_infos(
                        model_infos,
                        capability["capabilityId"],
                        capability["value"],
                    )

                    if capability_infos is None and self._create_unknown:
                        capability_infos = {
                            "capabilityId": capability["capabilityId"],
                            "name": "Capability_"
                            + str(capability["capabilityId"]),
                            "type": "string",
                            "category": "diag",
                        }

                    if capability_infos is not None and len(capability_infos) > 0:
                        capability_infos["deviceId"] = deviceId

                        is_duplicate = False

                        if "capabilityDuplicate" in capability_infos:
                            for cap in capabilities:
                                if (
                                    cap["capabilityId"]
                                    == capability_infos["capabilityDuplicate"]
                                ):
                                    is_duplicate = True
                                    break

                        if not is_duplicate:
                            capabilities.append(capability_infos)

        return capabilities

    def get_capability_infos(
        self,
        modelId: int,
        capabilityId: int,
        capabilityValue: str,
    ):
        """Get capability information."""
        return get_capability_infos(
            modelId,
            capabilityId,
            capabilityValue,
        )

    def get_capability_value(
        self,
        capabilityId: int,
        defaultIfNotExist: str | None = "0",
    ):
        """Get value for a device capability."""
        for dev in self._devices:
            if dev["deviceId"] == self._deviceId:
                for capability in dev["capabilities"]:
                    if capabilityId == capability["capabilityId"]:
                        return capability["value"]

                return defaultIfNotExist

        return None

    async def set_capability_value(self, capabilityId: int, value: str):
        """Set value for a device capability."""
        if self._is_overkiz:
            _LOGGER.warning(
                "Atlantic capabilities are not used for Overkiz devices"
            )
            return

        _LOGGER.debug(
            "Set_capability_value for %s : %s = %s",
            self._deviceId,
            capabilityId,
            value,
        )

        if self.online:
            for dev in self._devices:
                if dev["deviceId"] == self._deviceId:
                    for capability in dev["capabilities"]:
                        if capabilityId == capability["capabilityId"]:
                            if self._test_load:
                                capability["value"] = value
                            else:
                                async with self._session.post(
                                    COZYTOUCH_ATLANTIC_API
                                    + "/magellan/executions/writecapability",
                                    json={
                                        "capabilityId": capabilityId,
                                        "deviceId": self._deviceId,
                                        "value": value,
                                    },
                                    headers={
                                        "Authorization": (
                                            f"Bearer {self._access_token}"
                                        ),
                                        "Content-Type": "application/json",
                                    },
                                ) as response:
                                    if response.status == 201:
                                        execution_id = await response.json()
                                        completed = False
                                        nb_retry = 0

                                        while not completed:
                                            async with self._session.get(
                                                COZYTOUCH_ATLANTIC_API
                                                + "/magellan/executions/"
                                                + str(execution_id),
                                                headers={
                                                    "Authorization": (
                                                        f"Bearer {self._access_token}"
                                                    ),
                                                    "Content-Type": (
                                                        "application/json"
                                                    ),
                                                },
                                            ) as execution_response:
                                                try:
                                                    execution_data = (
                                                        await execution_response.json()
                                                    )
                                                    execution_state = (
                                                        execution_data.get(
                                                            "state",
                                                            False,
                                                        )
                                                    )

                                                    if execution_state in (1, 2):
                                                        _LOGGER.info(
                                                            "Execution in progress"
                                                        )
                                                    elif execution_state == 3:
                                                        _LOGGER.info(
                                                            "Execution completed"
                                                        )
                                                        completed = True
                                                        break
                                                    else:
                                                        _LOGGER.error(
                                                            "Execution error"
                                                        )
                                                        break

                                                except ContentTypeError:
                                                    self.online = False
                                                    break

                                            nb_retry += 1
                                            if nb_retry > 5:
                                                break

                                            await asyncio.sleep(1)

                                        if completed:
                                            capability["value"] = value
                            break

    def away_mode_init(self, timestampStart, timestampEnd):
        """Initialize away mode timestamps."""
        self._timestamp_away_mode_start = timestampStart
        self._timestamp_away_mode_end = timestampEnd

    async def set_away_mode_start(
        self,
        capabilityIdTimestamps: int,
        timestamp,
    ):
        """Set away mode start timestamp."""
        self._timestamp_away_mode_start = timestamp
        self._timestamps_away_mode_capability_id = capabilityIdTimestamps
        self._timestamp_away_mode_last_change = datetime.now(
            tz=dt_util.DEFAULT_TIME_ZONE
        ).timestamp()

    def get_away_mode_start(self):
        """Get away mode start timestamp."""
        return self._timestamp_away_mode_start

    async def set_away_mode_end(
        self,
        capabilityIdTimestamps: int,
        timestamp,
    ):
        """Set away mode end timestamp."""
        self._timestamp_away_mode_end = timestamp
        self._timestamps_away_mode_capability_id = capabilityIdTimestamps
        self._timestamp_away_mode_last_change = datetime.now(
            tz=dt_util.DEFAULT_TIME_ZONE
        ).timestamp()

    def get_away_mode_end(self):
        """Get away mode end timestamp."""
        return self._timestamp_away_mode_end

    async def set_away_mode_timestamps(
        self,
        capabilityIdMode,
        valueMode,
        capabilityIdTimestamps: int,
        timestampStart,
        timestampEnd,
    ):
        """Set away mode timestamps."""
        if self.online and not self._is_overkiz:
            json_data = {}

            for key in (
                "address",
                "area",
                "currency",
                "mainHeatingEnergy",
                "mainDHWEnergy",
                "name",
                "numberOfPersons",
                "numberOfRooms",
                "setupBuildingDate",
                "type",
            ):
                if key in self._setup:
                    json_data[key] = copy.deepcopy(self._setup[key])

            json_data["absence"] = {}

            if timestampStart is not None and timestampEnd is not None:
                json_data["absence"]["startDate"] = timestampStart
                json_data["absence"]["endDate"] = timestampEnd

            async with self._session.put(
                COZYTOUCH_ATLANTIC_API
                + "/magellan/v2/setups/"
                + str(self._setup["id"]),
                json=json_data,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
            ) as response:
                if response.status in (200, 204):
                    if timestampStart is not None and timestampEnd is not None:
                        value_timestamps = (
                            "[" + str(timestampStart) + "," + str(timestampEnd) + "]"
                        )
                        await self.set_capability_value(
                            capabilityIdTimestamps,
                            value_timestamps,
                        )
                        _LOGGER.info(
                            "Away mode enabled %d -> %d",
                            timestampStart,
                            timestampEnd,
                        )
                    else:
                        await self.set_capability_value(
                            capabilityIdTimestamps,
                            "[0,0]",
                        )
                        _LOGGER.info("Away mode disabled")

                    if capabilityIdMode is not None and valueMode is not None:
                        await self.set_capability_value(
                            capabilityIdMode,
                            valueMode,
                        )

                    self._timestamp_away_mode_last_change = None
                else:
                    _LOGGER.error(
                        "Set away mode: response %d (%s)",
                        response.status,
                        str(response.request_info),
                    )

    async def _update_localization(self, country: str):
        """Update localization information."""
        if len(self._localization) == 0:
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }

            async with self._session.get(
                COZYTOUCH_ATLANTIC_API + "/magellan/refs/countries",
                headers=headers,
            ) as response:
                try:
                    json_data = await response.json()

                    if isinstance(json_data, list):
                        for localization in json_data:
                            if localization.get("countryCode", "") == country:
                                self._localization = copy.deepcopy(localization)
                                break

                except ContentTypeError:
                    self._localization = {}


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""