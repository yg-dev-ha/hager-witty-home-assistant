from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    DOMAIN,
)
from .coordinator import HagerWittyCoordinator


class HagerWittyEntity(CoordinatorEntity[HagerWittyCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: HagerWittyCoordinator, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = str(entry.data[CONF_DEVICE_ID])
        self._attr_unique_id = f"{self._device_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Hager",
            model="Witty Start",
            name=str(entry.data.get(CONF_DEVICE_NAME) or "Witty Start"),
        )
