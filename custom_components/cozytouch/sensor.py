
"""Sensors for Atlantic Cozytouch and Sauter Pagosa integration."""

from __future__ import annotations

import datetime
import json
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CozytouchCapabilityVariableType
from .hub import Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cozytouch sensors."""
    _LOGGER.debug("%s: setting up sensor platform", config_entry.title)

    try:
        hub = hass.data[DOMAIN][config_entry.entry_id]
    except KeyError:
        _LOGGER.error(
            "%s: cannot initialise sensors: hub not found",
            config_entry.title,
        )
        return

    sensors = []

    # Sauter Pagosa connected through Overkiz.
    if hub.is_overkiz():
        states = hub.get_overkiz_states()

        if not isinstance(states, dict):
            states = {}

        pagosa_sensors = [
            {
                "state": "core:TemperatureState",
                "name": "Température de l'eau",
                "icon": "mdi:thermometer",
                "device_class": SensorDeviceClass.TEMPERATURE,
                "unit": UnitOfTemperature.CELSIUS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "state": "core:TargetTemperatureState",
                "name": "Température cible",
                "icon": "mdi:thermometer-check",
                "device_class": SensorDeviceClass.TEMPERATURE,
                "unit": UnitOfTemperature.CELSIUS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "state": "core:ComfortTargetTemperatureState",
                "name": "Température de confort",
                "icon": "mdi:thermometer-plus",
                "device_class": SensorDeviceClass.TEMPERATURE,
                "unit": UnitOfTemperature.CELSIUS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "state": "core:EcoTargetTemperatureState",
                "name": "Température éco",
                "icon": "mdi:thermometer-minus",
                "device_class": SensorDeviceClass.TEMPERATURE,
                "unit": UnitOfTemperature.CELSIUS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "state": "core:FrostProtectionTargetTemperatureState",
                "name": "Température hors gel",
                "icon": "mdi:snowflake-thermometer",
                "device_class": SensorDeviceClass.TEMPERATURE,
                "unit": UnitOfTemperature.CELSIUS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "state": "core:HaltedTargetTemperatureState",
                "name": "Température en arrêt",
                "icon": "mdi:thermometer-off",
                "device_class": SensorDeviceClass.TEMPERATURE,
                "unit": UnitOfTemperature.CELSIUS,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "state": "io:DHWCapacityState",
                "name": "Capacité du ballon",
                "icon": "mdi:water",
                "device_class": SensorDeviceClass.VOLUME,
                "unit": UnitOfVolume.LITERS,
            },
            {
                "state": "core:WaterConsumptionState",
                "name": "Consommation d'eau",
                "icon": "mdi:water-outline",
            },
            {
                "state": "io:HeatPumpOperatingTimeState",
                "name": "Temps de fonctionnement pompe à chaleur",
                "icon": "mdi:clock-outline",
            },
            {
                "state": "io:ElectricBoosterOperatingTimeState",
                "name": "Temps de fonctionnement appoint électrique",
                "icon": "mdi:clock-time-four-outline",
            },
            {
                "state": "core:RSSILevelState",
                "name": "Puissance du signal radio",
                "icon": "mdi:wifi",
            },
            {
                "state": "core:DiscreteRSSILevelState",
                "name": "Qualité du signal radio",
                "icon": "mdi:wifi-strength-2",
            },
            {
                "state": "core:StatusState",
                "name": "État de connexion du chauffe-eau",
                "icon": "mdi:connection",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "core:ManufacturerNameState",
                "name": "Fabricant",
                "icon": "mdi:factory",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "core:NameState",
                "name": "Nom de l'appareil",
                "icon": "mdi:tag",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "core:VersionState",
                "name": "Version matérielle",
                "icon": "mdi:chip",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "core:OperatingModeState",
                "name": "État des modes de fonctionnement",
                "icon": "mdi:state-machine",
            },
            {
                "state": "core:CommandLockLevelsState",
                "name": "Verrouillages des commandes",
                "icon": "mdi:lock",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "core:PriorityLockTimerState",
                "name": "Durée du verrouillage prioritaire",
                "icon": "mdi:timer-lock",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "core:SecuredPositionTemperatureState",
                "name": "Température de sécurité",
                "icon": "mdi:shield-thermometer",
                "device_class": SensorDeviceClass.TEMPERATURE,
                "unit": UnitOfTemperature.CELSIUS,
            },
            {
                "state": "io:DHWModeState",
                "name": "Mode de fonctionnement ECS",
                "icon": "mdi:water-boiler",
            },
            {
                "state": "io:OperatingRangeState",
                "name": "Plage de fonctionnement",
                "icon": "mdi:tune",
            },
            {
                "state": "io:AntiLegionellosisState",
                "name": "Protection anti-légionellose",
                "icon": "mdi:shield-check",
            },
            {
                "state": "io:ElectricalExtraManagementState",
                "name": "Gestion appoint électrique",
                "icon": "mdi:flash",
            },
            {
                "state": "io:InstallationState",
                "name": "Type d'installation",
                "icon": "mdi:home-lightning-bolt",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "io:BoilerInstallationOptionState",
                "name": "Option d'installation",
                "icon": "mdi:cog",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "io:SmartGridOptionState",
                "name": "Option Smart Grid",
                "icon": "mdi:transmission-tower",
            },
            {
                "state": "io:ExtractionOptionState",
                "name": "Option d'extraction",
                "icon": "mdi:fan",
            },
            {
                "state": "io:RateManagementState",
                "name": "Gestion tarifaire",
                "icon": "mdi:currency-eur",
            },
            {
                "state": "io:AwayModeDurationState",
                "name": "Durée du mode absence",
                "icon": "mdi:calendar-clock",
            },
            {
                "state": "core:BoostModeDurationState",
                "name": "Durée du mode Boost",
                "icon": "mdi:rocket-launch",
            },
            {
                "state": "io:OperatingModeCapabilitiesState",
                "name": "Fonctions disponibles",
                "icon": "mdi:list-box",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "io:DHWErrorState",
                "name": "Erreur chauffe-eau",
                "icon": "mdi:alert-circle-outline",
                "entity_category": EntityCategory.DIAGNOSTIC,
            },
            {
                "state": "io:ProgrammingSlotsState",
                "name": "Programmation horaire",
                "icon": "mdi:calendar-clock",
            },
            {
                "state": "io:ElectricalExtraManagementState",
                "name": "Gestion appoint électrique",
                "icon": "mdi:lightning-bolt",
            },
            {
                "state": "io:SmartGridOptionState",
                "name": "Configuration Smart Grid",
                "icon": "mdi:transmission-tower",
            },
            {
                "state": "io:BoilerInstallationOptionState",
                "name": "Configuration chaudière",
                "icon": "mdi:water-boiler-auto",
            },
            {
                "state": "io:ExtractionOptionState",
                "name": "Configuration extraction",
                "icon": "mdi:fan",
            },
        ]

        seen_states = set()

        for description in pagosa_sensors:
            state_key = description["state"]

            if state_key in seen_states or state_key not in states:
                continue

            seen_states.add(state_key)

            sensors.append(
                OverkizPagosaSensor(
                    coordinator=hub,
                    config_entry=config_entry,
                    state_key=state_key,
                    description=description,
                )
            )

        # Energy meter is a separate Overkiz device (#2).
        energy_states = hub.get_overkiz_energy_states()

        if not isinstance(energy_states, dict):
            energy_states = {}

        energy_sensors = [
            {
                "state": "core:ElectricEnergyConsumptionState",
                "name": "Consommation électrique totale",
                "icon": "mdi:lightning-bolt",
            },
            {
                "state": "core:ElectricEnergyConsumptionInTariff1State",
                "name": "Consommation électrique tarif 1",
                "icon": "mdi:lightning-bolt-outline",
            },
            {
                "state": "core:ElectricEnergyConsumptionInTariff2State",
                "name": "Consommation électrique tarif 2",
                "icon": "mdi:lightning-bolt-outline",
            },
        ]

        for description in energy_sensors:
            state_key = description["state"]

            if state_key not in energy_states:
                continue

            sensors.append(
                OverkizPagosaEnergySensor(
                    coordinator=hub,
                    config_entry=config_entry,
                    state_key=state_key,
                    description=description,
                )
            )

        if sensors:
            _LOGGER.info(
                "%s: adding %d Pagosa Overkiz sensors",
                config_entry.title,
                len(sensors),
            )

            _LOGGER.info(
                "%s: found %d Pagosa energy states",
                config_entry.title,
                sum(
                    1
                    for item in energy_sensors
                    if item["state"] in energy_states
                ),
            )

            async_add_entities(sensors, True)
        else:
            _LOGGER.warning(
                "%s: no Pagosa states available to create sensors",
                config_entry.title,
            )

        return

    # Classic Atlantic Cozytouch devices.
    capabilities = hub.get_capabilities_for_device(
        config_entry.data["deviceId"]
    )

    for capability in capabilities:
        if capability["type"] in ("string", "int"):
            sensors.append(
                CozytouchSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                )
            )

        elif capability["type"] == "temperature":
            sensors.append(
                CozytouchUnitSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                )
            )

        elif capability["type"] == "pressure":
            sensors.append(
                CozytouchUnitSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                    device_class=SensorDeviceClass.PRESSURE,
                    native_unit_of_measurement=UnitOfPressure.BAR,
                )
            )

        elif capability["type"] == "away_mode_timestamps":
            for index in (0, 1):
                sensors.append(
                    CozytouchAwayModeTimestampSensor(
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                        attr_uniq_id=f"{config_entry.entry_id}_{index}",
                        coordinator=hub,
                        name=capability[f"name_{index}"],
                        icon=capability.get(f"icon_{index}"),
                        separator=",",
                        timestamp_index=index,
                    )
                )

        elif capability["type"] in ("switch", "binary"):
            sensors.append(
                CozytouchBinarySensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                )
            )

        elif capability["type"] == "away_mode_switch":
            sensors.append(
                CozytouchAwayModeSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                )
            )

        elif capability["type"] == "signal":
            sensors.append(
                CozytouchUnitSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                    native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
                )
            )

        elif capability["type"] == "power":
            sensors.append(
                CozytouchUnitSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                    device_class=SensorDeviceClass.POWER,
                    native_unit_of_measurement=capability.get(
                        "displayed_unit_of_measurement",
                        UnitOfPower.WATT,
                    ),
                    displayed_unit_of_measurement=capability.get(
                        "displayed_unit_of_measurement"
                    ),
                )
            )

        elif capability["type"] == "energy":
            native_unit = capability.get(
                "displayed_unit_of_measurement",
                UnitOfEnergy.WATT_HOUR,
            )
            display_factor = (
                0.001
                if native_unit == UnitOfEnergy.KILO_WATT_HOUR
                else 1.0
            )

            sensors.append(
                CozytouchUnitSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                    device_class=SensorDeviceClass.ENERGY,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    native_unit_of_measurement=native_unit,
                    display_factor=display_factor,
                )
            )

        elif capability["type"] == "volume":
            sensors.append(
                CozytouchUnitSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                    device_class=SensorDeviceClass.VOLUME,
                    native_unit_of_measurement=UnitOfVolume.LITERS,
                )
            )

        elif capability["type"] == "water_consumption":
            sensors.append(
                CozytouchUnitSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                    device_class=SensorDeviceClass.WATER,
                    native_unit_of_measurement=UnitOfVolume.LITERS,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                )
            )

        elif capability["type"] == "percentage":
            sensors.append(
                CozytouchUnitSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                    device_class=SensorDeviceClass.BATTERY,
                    native_unit_of_measurement=PERCENTAGE,
                )
            )

        elif capability["type"] == "time":
            sensors.append(
                CozytouchTimeSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                )
            )

        elif capability["type"] == "timezone":
            sensors.append(
                CozytouchTimezoneSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                )
            )

        elif capability["type"] == "prog":
            sensors.append(
                CozytouchProgSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                )
            )

        elif capability["type"] == "progtime":
            sensors.append(
                CozytouchProgTimeSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                )
            )

        elif capability["type"] == "climate":
            sensors.append(
                CozytouchSensor(
                    capability=capability,
                    config_title=config_entry.title,
                    config_uniq_id=config_entry.entry_id,
                    coordinator=hub,
                )
            )

    if sensors:
        async_add_entities(sensors, True)


class OverkizPagosaSensor(CoordinatorEntity[Hub], SensorEntity):
    """Sensor based on an Overkiz state of a Sauter Pagosa."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Hub,
        config_entry: ConfigEntry,
        state_key: str,
        description: dict,
    ) -> None:
        """Initialize a Pagosa sensor."""
        super().__init__(coordinator)

        self._state_key = state_key
        self._config_entry = config_entry

        self._attr_name = description["name"]
        self._attr_icon = description.get("icon")
        self._attr_unique_id = (
            f"{DOMAIN}_{config_entry.entry_id}_overkiz_"
            f"{state_key.replace(':', '_')}"
        )

        self._attr_native_unit_of_measurement = description.get("unit")
        self._attr_device_class = description.get("device_class")
        self._attr_state_class = description.get("state_class")
        self._attr_entity_category = description.get("entity_category")

        device = coordinator.get_overkiz_device() or {}
        self._device_identifier = str(
            device.get("deviceURL", config_entry.entry_id)
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return Pagosa device information."""
        device = self.coordinator.get_overkiz_device() or {}

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_identifier)},
            manufacturer="Sauter",
            name=device.get("label") or self._config_entry.title,
            model="Pagosa 270L",
        )

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return (
            self.coordinator.last_update_success
            and self._state_key in self.coordinator.get_overkiz_states()
        )

    @property
    def native_value(self):
        """Return the current state value."""
        value = self.coordinator.get_overkiz_state(self._state_key)

        if value is None:
            return None

        if isinstance(value, (dict, list)):
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )

        if isinstance(value, (int, float, bool)):
            return value

        return str(value)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor when the coordinator refreshes."""
        self.async_write_ha_state()


class OverkizPagosaEnergySensor(CoordinatorEntity[Hub], SensorEntity):
    """Energy sensor from the separate Pagosa Overkiz energy device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: Hub,
        config_entry: ConfigEntry,
        state_key: str,
        description: dict,
    ) -> None:
        """Initialize energy sensor."""
        super().__init__(coordinator)

        self._state_key = state_key
        self._config_entry = config_entry
        self._attr_name = description["name"]
        self._attr_icon = description.get("icon")

        self._attr_unique_id = (
            f"{DOMAIN}_{config_entry.entry_id}_overkiz_energy_"
            f"{state_key.replace(':', '_')}"
        )

        # Keep the energy entities grouped with the main Pagosa device.
        device = coordinator.get_overkiz_device() or {}
        self._device_identifier = str(
            device.get("deviceURL", config_entry.entry_id)
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the same physical appliance as the Pagosa sensors."""
        device = self.coordinator.get_overkiz_device() or {}

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_identifier)},
            manufacturer="Sauter",
            name=device.get("label") or self._config_entry.title,
            model="Pagosa 270L",
        )

    @property
    def available(self) -> bool:
        """Return energy sensor availability."""
        return (
            self.coordinator.last_update_success
            and self._state_key
            in self.coordinator.get_overkiz_energy_states()
        )

    @property
    def native_value(self) -> float | None:
        """Convert the Overkiz Wh value to kWh."""
        value = self.coordinator.get_overkiz_energy_state(
            self._state_key
        )

        if value is None:
            return None

        try:
            return float(value) / 1000
        except (TypeError, ValueError):
            _LOGGER.warning(
                "Invalid energy value for %s: %s",
                self._state_key,
                value,
            )
            return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update energy sensor."""
        self.async_write_ha_state()


class CozytouchSensor(SensorEntity, CoordinatorEntity):
    """Common class for Cozytouch sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        attr_uniq_id: str | None = None,
        name: str | None = None,
        translation_key: str | None = None,
        icon: str | None = None,
        value_type: CozytouchCapabilityVariableType | None = None,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(coordinator)

        self._capability = capability
        self._config_title = config_title
        self._config_uniq_id = config_uniq_id
        self._last_value = None
        self._device_uniq_id = config_uniq_id

        if value_type:
            self._value_type = value_type
        elif "value_type" in self._capability:
            self._value_type = self._capability["value_type"]
        else:
            self._value_type = None

        if attr_uniq_id:
            self._attr_unique_id = attr_uniq_id
        else:
            capability_id = self._capability["capabilityId"]
            self._attr_unique_id = (
                f"{DOMAIN}_{config_uniq_id}_{str(capability_id)}"
            )

        self.entity_description = SensorEntityDescription(
            key="capability_" + str(capability["capabilityId"]),
            name=name if name else self._capability["name"],
        )

        self._attr_translation_key = (
            translation_key if translation_key else self.entity_description.name
        )

        if "category" in self._capability:
            if self._capability["category"] == "diag":
                self._attr_entity_category = EntityCategory.DIAGNOSTIC
            elif self._capability["category"] == "config":
                self._attr_entity_category = EntityCategory.CONFIG
            else:
                self._attr_entity_category = None

        if icon:
            self._attr_icon = icon
        elif "icon" in self._capability:
            self._attr_icon = self._capability["icon"]

    def get_value(self):
        """Retrieve value from hub."""
        if self._value_type == CozytouchCapabilityVariableType.ARRAY:
            return "array"

        try:
            value = self.coordinator.get_capability_value(
                self._capability["capabilityId"]
            )

            if value is None:
                return None

            if self._value_type == CozytouchCapabilityVariableType.BOOL:
                return bool(value)

            if self._value_type == CozytouchCapabilityVariableType.FLOAT:
                return float(value)

            if self._value_type == CozytouchCapabilityVariableType.INT:
                return int(value)

        except (ValueError, TypeError):
            return value

        return value

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        model_infos = self.coordinator.get_model_infos()

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_uniq_id)},
            manufacturer="Atlantic",
            name=model_infos["name"],
            model=model_infos["name"],
            serial_number=self.coordinator.get_serial_number(),
        )

    @property
    def native_value(self):
        """Return sensor value."""
        return self._last_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor value from the hub."""
        value = self.get_value()

        if value is None:
            if self._attr_available and not self.coordinator.online:
                _LOGGER.debug(
                    "%s: marking %s unavailable: Cozytouch connection lost",
                    self._config_title,
                    self._attr_name,
                )
                self._attr_available = False

        elif not self._attr_available:
            _LOGGER.info(
                "%s: marking %s available",
                self._config_title,
                self._attr_name,
            )
            self._attr_available = True

        self._last_value = value
        self.async_write_ha_state()


class CozytouchAwayModeTimestampSensor(CozytouchSensor):
    """Sensor for away mode timestamps."""

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
        """Initialize timestamp sensor."""
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

    def get_value(self) -> str | None:
        """Retrieve timestamp from hub."""
        value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )

        if value is None:
            return None

        try:
            value = value.translate(str.maketrans("", "", "[]"))
            timestamps = value.split(self._separator, 2)

            if len(timestamps) == 2:
                if timestamps[0] != "0" and timestamps[1] != "0":
                    timestamp = int(timestamps[self._timestamp_index])

                    time_offset = int(
                        self.coordinator.get_capability_value(
                            self._capability["timezoneCapabilityId"]
                        )
                    )

                    ts = datetime.datetime.fromtimestamp(
                        timestamp + time_offset
                    )

                    timestamp_start = self.coordinator.get_away_mode_start()
                    timestamp_end = self.coordinator.get_away_mode_end()

                    if timestamp_start is None or timestamp_end is None:
                        self.coordinator.away_mode_init(
                            int(timestamps[0]),
                            int(timestamps[1]),
                        )

                    return ts.strftime("%H:%M %d/%m/%Y")

                return "Undefined"

        except (ValueError, TypeError, IndexError):
            _LOGGER.warning("Invalid away mode timestamp: %s", value)

        return None


class CozytouchBinarySensor(BinarySensorEntity, CozytouchSensor):
    """Binary sensor for Cozytouch."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize binary sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

        self._last_value = False

    @property
    def is_on(self) -> bool:
        """Return last state value."""
        value_on = self._capability.get("value_on", "1")
        return self._last_value == value_on


class CozytouchAwayModeSensor(CozytouchSensor):
    """Sensor for away mode."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize away mode sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

    def get_value(self) -> str | None:
        """Retrieve away mode value."""
        value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )

        if value is None:
            return None

        if value == self._capability["value_off"]:
            return "Off"
        if value == self._capability["value_pending"]:
            return "Pending"
        if value == self._capability["value_on"]:
            return "On"

        return "Unknown"


class CozytouchUnitSensor(CozytouchSensor):
    """Sensor with a unit of measurement."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        device_class: SensorDeviceClass,
        native_unit_of_measurement,
        display_factor: float | None = 1.0,
        state_class: SensorStateClass | None = None,
        suggested_precision: int | None = None,
        name: str | None = None,
        icon: str | None = None,
        displayed_unit_of_measurement=None,
    ) -> None:
        """Initialize unit sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
            value_type=CozytouchCapabilityVariableType.FLOAT,
        )

        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_suggested_display_precision = suggested_precision

        if device_class:
            self._attr_device_class = device_class

        if state_class:
            self._attr_state_class = state_class

        self.displayed_unit_of_measurement = displayed_unit_of_measurement
        self._display_factor = display_factor

    def get_value(self):
        """Retrieve and convert value."""
        value = super().get_value()

        if value is not None and self._display_factor != 1.0:
            return float(value) * self._display_factor

        return value

    @property
    def native_value(self) -> float | None:
        """Return numeric sensor value."""
        if self._last_value is not None:
            try:
                return float(self._last_value)
            except (ValueError, TypeError):
                return None

        return None


class CozytouchTimeSensor(CozytouchSensor):
    """Sensor for time values expressed in minutes."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize time sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

        self._last_value = 0

    def get_value(self) -> str | None:
        """Retrieve and format time value."""
        value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )

        if value is None:
            return None

        remaining = int(value)
        days, remaining = divmod(remaining, 60 * 24)
        hours, minutes = divmod(remaining, 60)

        result = f"{hours:02d}:{minutes:02d}"

        if days > 0:
            result = f"{days}d {result}"

        return result


class CozytouchTimezoneSensor(CozytouchSensor):
    """Sensor for timezone offset."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize timezone sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

        self._last_value = 0

    def get_value(self) -> str | None:
        """Retrieve timezone offset."""
        value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )

        if value is None:
            return None

        offset = int(float(value))
        hours = abs(offset) // 3600
        minutes = (abs(offset) % 3600) // 60

        if offset > 0:
            return f"GMT+{hours:02d}:{minutes:02d}"
        if offset < 0:
            return f"GMT-{hours:02d}:{minutes:02d}"

        return "GMT"


class CozytouchProgSensor(CozytouchSensor):
    """Sensor for Cozytouch programming values."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize programming sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

    def get_value(self) -> str | None:
        """Retrieve programming values."""
        value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )

        if value is None:
            return None

        prog_list = json.loads(value)
        result = ""

        for prog in prog_list:
            if len(prog) >= 2 and (prog[0] != 0 or prog[1] != 0):
                hours, minutes = divmod(int(prog[0]), 60)

                if result:
                    result += " / "

                result += f"{hours:02d}:{minutes:02d} {int(prog[1])}°C"

        return result


class CozytouchProgTimeSensor(CozytouchSensor):
    """Sensor for Cozytouch programming time ranges."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize programming time sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

    def get_value(self) -> str | None:
        """Retrieve programming time ranges."""
        value = self.coordinator.get_capability_value(
            self._capability["capabilityId"]
        )

        if value is None:
            return None

        prog_list = json.loads(value)
        result = ""

        for prog in prog_list:
            if len(prog) >= 2 and (prog[0] != 0 or prog[1] != 0):
                start_hour, start_minute = divmod(int(prog[0]), 60)
                end_hour, end_minute = divmod(int(prog[1]), 60)

                if result:
                    result += " / "

                result += (
                    f"{start_hour:02d}:{start_minute:02d}-"
                    f"{end_hour:02d}:{end_minute:02d}"
                )

        return result
