from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HagerWittyEntity
from .models import is_charging


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WittyChargingBinarySensor(entry.runtime_data.coordinator, entry)])


class WittyChargingBinarySensor(HagerWittyEntity, BinarySensorEntity):
    _attr_translation_key = "charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "charging")

    @property
    def is_on(self) -> bool | None:
        return is_charging(self.coordinator.data)
