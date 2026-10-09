from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HagerWittyEntity
from .models import is_charge_control_available, is_charging, status_event_type
from .api import WittyAuthError, WittyError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WittyChargeSwitch(entry.runtime_data.coordinator, entry)])


class WittyChargeSwitch(HagerWittyEntity, SwitchEntity):
    """Single Start/Stop control for the EV charge."""

    _attr_translation_key = "charge"
    _attr_icon = "mdi:ev-plug-type2"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "charge")

    @property
    def available(self) -> bool:
        # 2006 = charger available, no vehicle plugged in: there is nothing to
        # start/stop. Unknown states are deliberately left unavailable until we
        # capture and classify them instead of guessing.
        return super().available and is_charge_control_available(self.coordinator.data)

    @property
    def is_on(self) -> bool | None:
        return is_charging(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_control("start")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_control("stop")

    async def _async_control(self, action: str) -> None:
        if not self.available:
            raise HomeAssistantError("Charging control is unavailable for the current charger state")
        _LOGGER.info(
            "Hager Witty %s command requested: current_event_type=%s",
            action,
            status_event_type(self.coordinator.data),
        )
        try:
            await self.coordinator.api.async_control(self._device_id, action)
        except WittyAuthError:
            self._entry.async_start_reauth(self.hass)
            raise HomeAssistantError("Reconnect the Hager integration before controlling charging") from None
        except WittyError as err:
            raise HomeAssistantError(f"Hager did not confirm the {action} command: {err}") from None
        await self.coordinator.async_request_refresh()
