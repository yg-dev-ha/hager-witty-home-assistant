from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import (
    API_BASE,
    APIM_SUBSCRIPTION_KEY,
    AUDIENCE,
    CLIENT_ID,
    DISCOVERY_URL,
    REDIRECT_URI,
    SCOPE,
)

TokenUpdateCallback = Callable[[dict[str, Any]], Awaitable[None]]

_LOGGER = logging.getLogger(__name__)


class WittyError(Exception):
    """Base exception for Hager Witty."""


class WittyAuthError(WittyError):
    """Authentication or token refresh failed definitively."""


class WittyHttpAuthError(WittyAuthError):
    """HTTP authentication response with status and decoded payload."""

    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self.payload = payload
        # Response bodies may contain account data or OAuth credentials.
        super().__init__(f"Hager authentication response (HTTP {status})")


class WittyConnectionError(WittyError):
    """Network/API connectivity failed."""


class WittyApiError(WittyError):
    """Hager API returned an unexpected response."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def new_pkce() -> tuple[str, str, str, str]:
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = _b64url(secrets.token_bytes(24))
    nonce = _b64url(secrets.token_bytes(24))
    return verifier, challenge, state, nonce


def parse_authorization_input(value: str, expected_state: str | None = None) -> str:
    """Accept either the raw code or the full Android callback URI."""
    value = value.strip()
    if not value:
        raise WittyAuthError("Empty authorization code")
    if ":" not in value and "?" not in value and "&" not in value and not value.startswith("code="):
        return value

    parsed = urlparse(value)
    redirect = urlparse(REDIRECT_URI)
    if (parsed.scheme, parsed.netloc, parsed.path) != (
        redirect.scheme, redirect.netloc, redirect.path
    ):
        raise WittyAuthError("Unexpected OAuth callback URI")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if query.get("error"):
        raise WittyAuthError("Hager authorization was not completed")
    code = query.get("code", [None])[0]
    state = query.get("state", [None])[0]
    if not code or len(query["code"]) != 1:
        raise WittyAuthError("No authorization code found in callback URL")
    if expected_state and (len(query.get("state", [])) != 1 or state != expected_state):
        raise WittyAuthError("OAuth state mismatch")
    return str(code)


class HagerWittyApi:
    def __init__(
        self,
        session: ClientSession,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
        expires_at: float = 0,
        token_endpoint: str | None = None,
        token_update_callback: TokenUpdateCallback | None = None,
    ) -> None:
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = float(expires_at or 0)
        self._token_endpoint = token_endpoint
        self._token_update_callback = token_update_callback
        self._refresh_lock = asyncio.Lock()

    @property
    def expires_at(self) -> float:
        return self._expires_at

    async def _read_response(self, response: ClientResponse) -> Any:
        text = await response.text()
        if not text:
            return None
        try:
            return await response.json(content_type=None)
        except (ValueError, ClientError):
            return text

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: Any = None,
        timeout: int = 30,
        auth_error_statuses: frozenset[int] = frozenset({400, 401, 403}),
    ) -> tuple[int, Any]:
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                data=data,
                timeout=timeout,
                allow_redirects=False,
            ) as response:
                payload = await self._read_response(response)
                if response.status >= 400:
                    if response.status in auth_error_statuses:
                        raise WittyHttpAuthError(response.status, payload)
                    raise WittyApiError(f"Hager request failed (HTTP {response.status})")
                if 300 <= response.status < 400:
                    raise WittyApiError("Unexpected HTTP redirect from Hager")
                return response.status, payload
        except WittyError:
            raise
        except (ClientError, asyncio.TimeoutError) as err:
            raise WittyConnectionError("Unable to communicate with Hager") from None

    async def async_discovery(self) -> dict[str, Any]:
        _, payload = await self._request_json("GET", DISCOVERY_URL)
        if not isinstance(payload, dict):
            raise WittyApiError("OIDC discovery did not return JSON")
        for key in ("authorization_endpoint", "token_endpoint"):
            if not payload.get(key):
                raise WittyApiError(f"OIDC discovery is missing {key}")
        return payload

    async def async_build_authorization_url(
        self,
        *,
        country: str,
        locale: str,
        challenge: str,
        state: str,
        nonce: str,
    ) -> tuple[str, str]:
        discovery = await self.async_discovery()
        token_endpoint = str(discovery["token_endpoint"])
        acr = f"type:APP brand:HAG target:B2C app:WITTY country:{country.upper()}"
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "audience": AUDIENCE,
            "ui_locales": locale,
            "acr_values": acr,
            "prompt": "login",
        }
        auth_endpoint = str(discovery["authorization_endpoint"])
        separator = "&" if "?" in auth_endpoint else "?"
        return auth_endpoint + separator + urlencode(params), token_endpoint

    async def async_exchange_code(
        self,
        *,
        code: str,
        verifier: str,
        token_endpoint: str,
    ) -> dict[str, Any]:
        body = urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": verifier,
            }
        )
        _, payload = await self._request_json(
            "POST",
            token_endpoint,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=body,
        )
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise WittyApiError("Token response is missing an access token")
        self._apply_token_payload(payload, token_endpoint=token_endpoint)
        return self.token_data()

    def _apply_token_payload(self, payload: dict[str, Any], *, token_endpoint: str) -> None:
        # Validate before replacing any token; malformed responses must not
        # discard the last usable credentials or trigger unnecessary reauth.
        try:
            expires_in = int(payload.get("expires_in", 0))
        except (ValueError, TypeError, OverflowError):
            raise WittyApiError("Invalid OAuth token lifetime") from None
        if expires_in <= 0 or not isinstance(payload.get("access_token"), str):
            raise WittyApiError("Invalid OAuth token response")
        self._access_token = payload["access_token"]
        if payload.get("refresh_token"):
            self._refresh_token = str(payload["refresh_token"])
        self._expires_at = time.time() + expires_in
        self._token_endpoint = token_endpoint

    def token_data(self) -> dict[str, Any]:
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_at": self._expires_at,
            "token_endpoint": self._token_endpoint,
        }

    async def async_refresh_tokens(
        self,
        *,
        force: bool = False,
        rejected_access_token: str | None = None,
    ) -> None:
        """Refresh OAuth tokens and persist token rotation.

        ``force`` is used after the Hager API rejects an access token with
        HTTP 401/403 even when its advertised expiry time has not passed.
        ``rejected_access_token`` prevents two concurrent callers from
        rotating the refresh token twice: if another caller already replaced
        the rejected token while we waited for the lock, there is nothing to
        do.
        """
        async with self._refresh_lock:
            if (
                force
                and rejected_access_token
                and self._access_token
                and self._access_token != rejected_access_token
            ):
                return
            if not force and self._access_token and self._expires_at > time.time() + 90:
                return
            if not self._refresh_token:
                raise WittyAuthError("No refresh token available")
            token_endpoint = self._token_endpoint
            if not token_endpoint:
                token_endpoint = str((await self.async_discovery())["token_endpoint"])

            _LOGGER.debug(
                "Refreshing Hager OAuth access token%s",
                " after API rejection" if force else "",
            )
            body = urlencode(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": CLIENT_ID,
                }
            )
            try:
                _, payload = await self._request_json(
                    "POST",
                    token_endpoint,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data=body,
                )
            except WittyHttpAuthError as err:
                error_code = (
                    str(err.payload.get("error", "")).lower()
                    if isinstance(err.payload, dict)
                    else ""
                )
                if error_code in {"invalid_grant", "invalid_token", "unauthorized_client"}:
                    raise WittyAuthError(
                        "Hager refresh token is invalid or expired"
                    ) from err
                # A gateway/policy/auth-looking response without a definitive
                # OAuth rejection must not force the user through login again.
                raise WittyConnectionError(
                    f"Hager token endpoint temporarily rejected refresh (HTTP {err.status})"
                ) from err

            if not isinstance(payload, dict) or not payload.get("access_token"):
                raise WittyApiError("Refresh response is missing an access token")
            self._apply_token_payload(payload, token_endpoint=token_endpoint)
            if self._token_update_callback:
                await self._token_update_callback(self.token_data())
            _LOGGER.debug("Hager OAuth access token refreshed and persisted")

    async def async_access_token(self) -> str:
        if not self._access_token or self._expires_at <= time.time() + 90:
            await self.async_refresh_tokens()
        if not self._access_token:
            raise WittyAuthError("No access token available")
        return self._access_token

    async def async_api_request(
        self,
        path: str,
        *,
        method: str = "GET",
        cache_policy: str | None = None,
    ) -> Any:
        """Call the Hager API, refreshing and retrying once on 401/403."""
        token = await self.async_access_token()

        async def _do_request(access_token: str) -> Any:
            headers = {
                "Authorization": "bearer " + access_token,
                "Ocp-Apim-Subscription-Key": APIM_SUBSCRIPTION_KEY,
                "Accept": "application/json",
            }
            if cache_policy:
                headers["CachePolicyId"] = cache_policy
            body = b"" if method == "POST" else None
            _, payload = await self._request_json(
                method,
                urljoin(API_BASE, path),
                headers=headers,
                data=body,
                # A resource-side HTTP 400 is an API/command error, not an
                # OAuth failure. Only 401/403 warrant a token refresh.
                auth_error_statuses=frozenset({401, 403}),
            )
            return payload

        try:
            return await _do_request(token)
        except WittyAuthError:
            _LOGGER.info(
                "Hager API rejected the access token; forcing OAuth refresh and retry"
            )

        # Hager can reject an access token before its advertised expires_at.
        # Always try the stored refresh token once before asking the user to
        # authenticate again.
        await self.async_refresh_tokens(
            force=True, rejected_access_token=token
        )
        if not self._access_token:
            raise WittyAuthError("No access token available after refresh")

        try:
            return await _do_request(self._access_token)
        except WittyHttpAuthError as err:
            # The refresh itself succeeded, so do not throw the user back into
            # OAuth just because the resource API still returns 401/403. A later
            # coordinator poll can retry; reauth is reserved for a definitively
            # rejected refresh token.
            raise WittyApiError(
                f"Hager API rejected the refreshed access token (HTTP {err.status})"
            ) from err

    async def async_get_user_data(self) -> dict[str, Any]:
        payload = await self.async_api_request("v1/EVCSDevice", cache_policy="NetworkFirst")
        if not isinstance(payload, dict):
            raise WittyApiError("EVCS response is not an object")
        device = self.get_device(payload)
        if not (device.get("Id") or device.get("id")):
            raise WittyApiError("EVCS response is missing the device id")
        return payload

    @staticmethod
    def get_device(data: dict[str, Any]) -> dict[str, Any]:
        device = data.get("Device") or data.get("device")
        if isinstance(device, dict):
            return device
        if "Id" in data or "id" in data:
            return data
        raise WittyApiError("Could not find Device object in EVCS response")

    async def async_control(self, device_id: str, action: str) -> None:
        if action not in ("start", "stop"):
            raise ValueError(action)
        path = f"v1/EVCSDevice/{quote(device_id, safe='')}/{action}-charging"
        await self.async_api_request(path, method="POST")
