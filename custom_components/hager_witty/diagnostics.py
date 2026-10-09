from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN
from .models import charging_session, device_from_data, status_event

TO_REDACT = {CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, "device_id", "device_name", "id", "name"}


def _value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _safe_device_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Return useful diagnostics without account/profile information or secrets."""
    device = device_from_data(data)
    event = status_event(data)
    session = charging_session(data)
    return {
        "device": {
            "id": _value(device, "Id", "id"),
            "name": _value(device, "Name", "name"),
            "type": _value(device, "Type", "type"),
            "status": _value(device, "Status", "status"),
            "charge_mode": _value(device, "ChargeMode", "chargeMode"),
            "connectivity_type": _value(device, "ConnectivityType", "connectivityType"),
            "locked": _value(device, "EvcsLocked", "evcsLocked"),
            "active": _value(device, "IsActive", "isActive"),
        },
        "status_event": {
            "timestamp": _value(event, "Timestamp", "timestamp"),
            "type": _value(event, "Type", "type"),
            "severity": _value(event, "Severity", "severity"),
            "short_description": _value(event, "ShortDescription", "shortDescription"),
            "long_description": _value(event, "LongDescription", "longDescription"),
        },
        "charging_session": {
            "energy": _value(session, "Energy", "energy"),
            "start": _value(session, "StartDate", "startDate"),
            "end": _value(session, "EndDate", "endDate"),
            "duration": _value(session, "Duration", "duration"),
            "charging_duration": _value(session, "ChargingDuration", "chargingDuration"),
            "speed": _value(session, "Speed", "speed"),
            "range_recovered": _value(session, "RangeRecoveredByEv", "rangeRecoveredByEv"),
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    runtime = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "charger": async_redact_data(_safe_device_snapshot(runtime.coordinator.data), TO_REDACT),
        "last_update_success": runtime.coordinator.last_update_success,
    }
