# Changelog

## 0.1.1 — Hager Cloud reliability

- Default polling interval increased from 10 seconds to 30 seconds.
- One safe retry with a 3-second backoff for idempotent status GET requests after network errors or HTTP 500/502/503/504 responses.
- Start/stop POST commands are not retried, avoiding duplicate charging commands after ambiguous cloud failures.
- Added offline regression tests for transient HTTP 500 and connection failures.

## 0.1.0 — Initial public release

- Hager Witty Start cloud integration with UI setup in English and French.
- Start/stop switch, charging state and session sensors.
- OAuth PKCE login, strict callback/state validation, synchronized token refresh and persisted rotation.
- One refresh/retry on API 401/403; transient API failures do not unnecessarily trigger reauthentication.
- Setup retry retains exchanged tokens; invalid device payloads and mismatched device IDs are rejected.
- Unknown charging states remain unknown and disable control.
- Redacted diagnostics and HTTP errors; no account profile in diagnostic exports.
- HACS metadata, local light/dark branding, installation package, issue forms and offline regression tests.

See the README for supported hardware, setup and current limitations.
