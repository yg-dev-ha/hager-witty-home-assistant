from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import HagerWittyEntity
from .models import charging_session, device_from_data, status_event_type

ValueFn = Callable[[dict[str, Any]], Any]


def _value(d: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in d:
            return d[key]
    return None


def _status(data: dict[str, Any]) -> str | int | None:
    dev = device_from_data(data)
    event = _value(dev, "StatusEvent", "statusEvent") or {}
    if isinstance(event, dict):
        text = _value(event, "ShortDescription", "shortDescription")
        if text:
            return str(text)
    return _value(dev, "Status", "status")


def _session_value(*keys: str) -> ValueFn:
    return lambda data: _value(charging_session(data), *keys)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(str(value))
    # Do not guess the timezone of an undocumented, naive cloud timestamp.
    return parsed if parsed is not None and parsed.tzinfo is not None else None


@dataclass(frozen=True, kw_only=True)
class WittySensorDescription(SensorEntityDescription):
    value_fn: ValueFn
    attrs_fn: ValueFn | None = None


SENSORS: tuple[WittySensorDescription, ...] = (
    WittySensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:ev-station",
        value_fn=_status,
        attrs_fn=lambda data: _status_attributes(data),
    ),
    WittySensorDescription(
        key="event_type",
        translation_key="event_type",
        icon="mdi:numeric",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=status_event_type,
        attrs_fn=lambda data: _status_attributes(data),
    ),
    WittySensorDescription(
        key="session_energy",
        translation_key="session_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        value_fn=_session_value("Energy", "energy"),
    ),
    WittySensorDescription(
        key="session_cost",
        translation_key="session_cost",
        icon="mdi:currency-eur",
        suggested_display_precision=2,
        value_fn=_session_value("Cost", "cost"),
    ),
    WittySensorDescription(
        key="session_duration",
        translation_key="session_duration",
        icon="mdi:timer-outline",
        value_fn=_session_value("Duration", "duration"),
    ),
    WittySensorDescription(
        key="charging_duration",
        translation_key="charging_duration",
        icon="mdi:timer-charging-outline",
        value_fn=_session_value("ChargingDuration", "chargingDuration"),
    ),
    WittySensorDescription(
        key="recovered_range",
        translation_key="recovered_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        value_fn=_session_value("RangeRecoveredByEv", "rangeRecoveredByEv"),
    ),
    WittySensorDescription(
        key="session_start",
        translation_key="session_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _parse_datetime(_session_value("StartDate", "startDate")(data)),
    ),
    WittySensorDescription(
        key="session_end",
        translation_key="session_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _parse_datetime(_session_value("EndDate", "endDate")(data)),
    ),
    WittySensorDescription(
        key="token_expiry",
        translation_key="token_expiry",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: None,
    ),
)


def _status_attributes(data: dict[str, Any]) -> dict[str, Any]:
    dev = device_from_data(data)
    event = _value(dev, "StatusEvent", "statusEvent") or {}
    attrs: dict[str, Any] = {
        "status_code": _value(dev, "Status", "status"),
        "serial_number": _value(dev, "SerialNumber", "serialNumber"),
    }
    if isinstance(event, dict):
        attrs.update(
            {
                "event_type": _value(event, "Type", "type"),
                "severity": _value(event, "Severity", "severity"),
                "description": _value(event, "LongDescription", "longDescription"),
                "event_timestamp": _value(event, "Timestamp", "timestamp"),
            }
        )
    return {key: value for key, value in attrs.items() if value is not None}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    async_add_entities(WittySensor(runtime.coordinator, entry, description) for description in SENSORS)


class WittySensor(HagerWittyEntity, SensorEntity):
    entity_description: WittySensorDescription

    def __init__(self, coordinator, entry, description: WittySensorDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description
        if description.key == "session_cost":
            self._attr_native_unit_of_measurement = coordinator.hass.config.currency

    @property
    def native_value(self):
        if self.entity_description.key == "token_expiry":
            expires_at = self._entry.data.get("expires_at")
            if not expires_at:
                return None
            return datetime.fromtimestamp(float(expires_at), tz=dt_util.UTC)
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        if self.entity_description.attrs_fn:
            return self.entity_description.attrs_fn(self.coordinator.data)
        return None
