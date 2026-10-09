from __future__ import annotations

import time
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

from .api import HagerWittyApi, WittyAuthError, WittyError, new_pkce, parse_authorization_input
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_AUTH_CODE,
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_EXPIRES_AT,
    CONF_LOCALE,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN_ENDPOINT,
    DEFAULT_COUNTRY,
    DEFAULT_LOCALE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


class HagerWittyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._country = DEFAULT_COUNTRY
        self._locale = DEFAULT_LOCALE
        self._verifier: str | None = None
        self._state: str | None = None
        self._token_endpoint: str | None = None
        self._auth_url: str | None = None
        self._reauth_entry = None
        self._authenticated_api: HagerWittyApi | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._country = str(user_input[CONF_COUNTRY]).upper()
            self._locale = str(user_input[CONF_LOCALE])
            try:
                await self._async_prepare_login()
            except WittyError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(user_input),
                    errors={"base": "cannot_connect"},
                )
            return await self.async_step_auth()

        return self.async_show_form(step_id="user", data_schema=self._user_schema())

    def _user_schema(self, values: dict[str, Any] | None = None) -> vol.Schema:
        values = values or {}
        return vol.Schema(
            {
                vol.Required(CONF_COUNTRY, default=values.get(CONF_COUNTRY, DEFAULT_COUNTRY)): str,
                vol.Required(CONF_LOCALE, default=values.get(CONF_LOCALE, DEFAULT_LOCALE)): str,
            }
        )

    async def _async_prepare_login(self) -> None:
        self._authenticated_api = None
        api = HagerWittyApi(async_get_clientsession(self.hass))
        verifier, challenge, state, nonce = new_pkce()
        auth_url, token_endpoint = await api.async_build_authorization_url(
            country=self._country,
            locale=self._locale,
            challenge=challenge,
            state=state,
            nonce=nonce,
        )
        self._verifier = verifier
        self._state = state
        self._token_endpoint = token_endpoint
        self._auth_url = auth_url

    async def async_step_auth(self, user_input: dict[str, Any] | None = None):
        if not self._auth_url or not self._verifier or not self._token_endpoint:
            try:
                await self._async_prepare_login()
            except WittyError:
                return self.async_abort(reason="cannot_connect")

        if user_input is None:
            return self.async_show_form(
                step_id="auth",
                description_placeholders={"auth_url": self._auth_url},
                data_schema=vol.Schema({vol.Required(CONF_AUTH_CODE): str}),
            )

        try:
            api = self._authenticated_api
            if api is None:
                code = parse_authorization_input(str(user_input[CONF_AUTH_CODE]), self._state)
                api = HagerWittyApi(async_get_clientsession(self.hass))
                await api.async_exchange_code(
                    code=code,
                    verifier=self._verifier,
                    token_endpoint=self._token_endpoint,
                )
                # A subsequent device lookup can fail temporarily. Keep tokens
                # in this flow so retrying never reuses a consumed OAuth code.
                self._authenticated_api = api
            user_data = await api.async_get_user_data()
            # The validation request above may itself force an OAuth refresh
            # (and Hager may rotate the refresh token). Persist the FINAL token
            # set, never the stale values returned by the first code exchange.
            tokens = api.token_data()
            device = api.get_device(user_data)
            device_id = str(device.get("Id") or device.get("id") or "")
            if not device_id:
                raise WittyError("No Witty device id returned")
            device_name = str(device.get("Name") or device.get("name") or "Witty Start")
        except WittyAuthError:
            self._authenticated_api = None
            return self.async_show_form(
                step_id="auth",
                description_placeholders={"auth_url": self._auth_url},
                data_schema=vol.Schema({vol.Required(CONF_AUTH_CODE): str}),
                errors={"base": "invalid_auth"},
            )
        except WittyError:
            return self.async_show_form(
                step_id="auth",
                description_placeholders={"auth_url": self._auth_url},
                data_schema=vol.Schema({vol.Required(CONF_AUTH_CODE): str}),
                errors={"base": "cannot_connect"},
            )

        data = {
            CONF_COUNTRY: self._country,
            CONF_LOCALE: self._locale,
            CONF_ACCESS_TOKEN: tokens.get("access_token"),
            CONF_REFRESH_TOKEN: tokens.get("refresh_token"),
            CONF_EXPIRES_AT: tokens.get("expires_at", time.time()),
            CONF_TOKEN_ENDPOINT: tokens.get("token_endpoint"),
            CONF_DEVICE_ID: device_id,
            CONF_DEVICE_NAME: device_name,
        }

        if self._reauth_entry is not None:
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._reauth_entry, data_updates=data
            )

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=device_name, data=data)

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if self._reauth_entry is None:
            return self.async_abort(reason="reauth_failed")
        self._country = str(entry_data.get(CONF_COUNTRY, DEFAULT_COUNTRY))
        self._locale = str(entry_data.get(CONF_LOCALE, DEFAULT_LOCALE))
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({}))
        try:
            await self._async_prepare_login()
        except WittyError:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
            )
        return await self.async_step_auth()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return HagerWittyOptionsFlow()


class HagerWittyOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = int(self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    )
                }
            ),
        )
