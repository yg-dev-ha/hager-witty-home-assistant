from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HagerWittyApi
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN_ENDPOINT,
    DEFAULT_SCAN_INTERVAL,
    PLATFORMS,
)
from .coordinator import HagerWittyCoordinator

PLATFORM_ENUMS = [Platform(platform) for platform in PLATFORMS]


@dataclass(slots=True)
class HagerWittyRuntimeData:
    api: HagerWittyApi
    coordinator: HagerWittyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    async def _save_tokens(tokens: dict[str, Any]) -> None:
        data = dict(entry.data)
        data.update(
            {
                CONF_ACCESS_TOKEN: tokens.get("access_token"),
                CONF_REFRESH_TOKEN: tokens.get("refresh_token"),
                CONF_EXPIRES_AT: tokens.get("expires_at", 0),
                CONF_TOKEN_ENDPOINT: tokens.get("token_endpoint"),
            }
        )
        hass.config_entries.async_update_entry(entry, data=data)

    api = HagerWittyApi(
        async_get_clientsession(hass),
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        expires_at=entry.data.get(CONF_EXPIRES_AT, 0),
        token_endpoint=entry.data.get(CONF_TOKEN_ENDPOINT),
        token_update_callback=_save_tokens,
    )
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    coordinator = HagerWittyCoordinator(hass, api, scan_interval, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = HagerWittyRuntimeData(api=api, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM_ENUMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORM_ENUMS)

