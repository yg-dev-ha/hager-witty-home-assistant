"""Pure helpers for the observed Hager charger payloads."""
from __future__ import annotations

from typing import Any

from .const import EVENT_VEHICLE_AVAILABLE, EVENT_VEHICLE_CHARGING, KNOWN_EVENT_TYPES


def _value(d: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in d:
            return d[key]
    return None


def device_from_data(data: dict[str, Any]) -> dict[str, Any]:
    dev = data.get("Device") or data.get("device")
    if isinstance(dev, dict):
        return dev
    return data


def status_event(data: dict[str, Any]) -> dict[str, Any]:
    dev = device_from_data(data)
    event = _value(dev, "StatusEvent", "statusEvent")
    return event if isinstance(event, dict) else {}


def status_event_type(data: dict[str, Any]) -> int | None:
    raw = _value(status_event(data), "Type", "type")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def charging_session(data: dict[str, Any]) -> dict[str, Any]:
    dev = device_from_data(data)
    session = _value(dev, "ChargingSession", "chargingSession")
    return session if isinstance(session, dict) else {}


def is_charging(data: dict[str, Any]) -> bool | None:
    """Return True only for the validated Hager 'vehicle charging' event.

    ChargingSession.EndDate == null cannot be used here: Hager keeps a session
    open while a vehicle is merely plugged in, even if charging is stopped.
    """
    event_type = status_event_type(data)
    if event_type not in KNOWN_EVENT_TYPES:
        return None
    return event_type == EVENT_VEHICLE_CHARGING


def is_charge_control_available(data: dict[str, Any]) -> bool:
    """Return True only for charger states validated as controllable.

    Unknown event types are intentionally not guessed. Once a new event code is
    captured in logs it can be classified explicitly.
    """
    return status_event_type(data) in {EVENT_VEHICLE_AVAILABLE, EVENT_VEHICLE_CHARGING}


