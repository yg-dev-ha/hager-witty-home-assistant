from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HagerWittyApi, WittyAuthError, WittyConnectionError, WittyError
from .const import CONF_DEVICE_ID, DEFAULT_SCAN_INTERVAL, DOMAIN, KNOWN_EVENT_TYPES

_LOGGER = logging.getLogger(__name__)


def _value(d: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in d:
            return d[key]
    return None


def _device(data: dict[str, Any]) -> dict[str, Any]:
    dev = data.get("Device") or data.get("device")
    return dev if isinstance(dev, dict) else data


def _safe_status_details(data: dict[str, Any]) -> dict[str, Any]:
    """Extract only non-secret status/session fields for logs."""
    dev = _device(data)
    event = _value(dev, "StatusEvent", "statusEvent") or {}
    session = _value(dev, "ChargingSession", "chargingSession") or {}
    if not isinstance(event, dict):
        event = {}
    if not isinstance(session, dict):
        session = {}
    return {
        "device_id": "[redacted]",
        "status": _value(dev, "Status", "status"),
        "event_type": _value(event, "Type", "type"),
        "severity": _value(event, "Severity", "severity"),
        "short_description": _value(event, "ShortDescription", "shortDescription"),
        "long_description": _value(event, "LongDescription", "longDescription"),
        "event_timestamp": _value(event, "Timestamp", "timestamp"),
        "session_energy": _value(session, "Energy", "energy"),
        "session_start": _value(session, "StartDate", "startDate"),
        "session_end": _value(session, "EndDate", "endDate"),
        "session_duration": _value(session, "Duration", "duration"),
        "charging_duration": _value(session, "ChargingDuration", "chargingDuration"),
        "speed": _value(session, "Speed", "speed"),
        "range_recovered": _value(session, "RangeRecoveredByEv", "rangeRecoveredByEv"),
    }


class HagerWittyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, api: HagerWittyApi, scan_interval: int, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval or DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self._device_id = str(entry.data[CONF_DEVICE_ID])
        self._last_status_signature: tuple[Any, ...] | None = None

    def _log_status(self, data: dict[str, Any]) -> None:
        details = _safe_status_details(data)
        signature = (
            details["status"],
            details["event_type"],
            details["severity"],
            details["short_description"],
        )

        # Full poll data is available when debug logging is enabled. No OAuth
        # token, API key, account secret or authorization code is logged here.
        _LOGGER.debug(
            "Hager Witty poll: device=%s status=%s event_type=%s severity=%s "
            "description=%r event_timestamp=%s energy=%s start=%s end=%s "
            "duration=%s charging_duration=%s speed=%s range_recovered=%s",
            details["device_id"],
            details["status"],
            details["event_type"],
            details["severity"],
            details["short_description"],
            details["event_timestamp"],
            details["session_energy"],
            details["session_start"],
            details["session_end"],
            details["session_duration"],
            details["charging_duration"],
            details["speed"],
            details["range_recovered"],
        )

        if signature == self._last_status_signature:
            return

        _LOGGER.info(
            "Hager Witty status transition: device=%s status=%s event_type=%s "
            "severity=%s description=%r event_timestamp=%s",
            details["device_id"],
            details["status"],
            details["event_type"],
            details["severity"],
            details["short_description"],
            details["event_timestamp"],
        )

        event_type = details["event_type"]
        try:
            event_type_int = int(event_type) if event_type is not None else None
        except (TypeError, ValueError):
            event_type_int = None

        if event_type is not None and event_type_int not in KNOWN_EVENT_TYPES:
            _LOGGER.warning(
                "Hager Witty UNKNOWN StatusEvent.Type observed: device=%s "
                "event_type=%s status=%s severity=%s description=%r "
                "long_description=%r event_timestamp=%s",
                details["device_id"],
                event_type,
                details["status"],
                details["severity"],
                details["short_description"],
                details["long_description"],
                details["event_timestamp"],
            )

        self._last_status_signature = signature

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.async_get_user_data()
            device = self.api.get_device(data)
            if str(device.get("Id") or device.get("id")) != self._device_id:
                raise UpdateFailed("Hager returned a different charger; check the account configuration")
            self._log_status(data)
            return data
        except WittyAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (WittyConnectionError, WittyError) as err:
            raise UpdateFailed(str(err)) from err
