<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.svg">
    <img src="docs/assets/logo.svg" alt="Hager Witty Start for Home Assistant" width="520">
  </picture>
</p>

<h1 align="center">Hager Witty Start · Home Assistant</h1>
<p align="center">See your charger. Follow your session. Start and stop charging from Home Assistant.</p>
<p align="center">
  <a href="https://github.com/yg-dev-ha/hager-witty-home-assistant/releases"><img alt="Release" src="https://img.shields.io/github/v/release/yg-dev-ha/hager-witty-home-assistant"></a>
  <a href="https://github.com/yg-dev-ha/hager-witty-home-assistant/actions/workflows/validate.yml"><img alt="Validation" src="https://github.com/yg-dev-ha/hager-witty-home-assistant/actions/workflows/validate.yml/badge.svg?branch=main"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-green"></a>
  <img alt="Home Assistant 2026.10 or later" src="https://img.shields.io/badge/Home_Assistant-2026.10%2B-41BDF5">
</p>
<p align="center"><strong>English</strong> · <a href="README.fr.md">Français</a></p>

Unofficial integration for **Hager Witty Start** chargers connected to **Hager Cloud**. Install it as a HACS custom repository to receive update notifications. Independent community project, not affiliated with or endorsed by Hager.

## At a glance

| Feature | v0.1.0 |
|---|---|
| Charging control | One **Charge** switch: start / stop |
| Live status | Cloud polling, every 10 seconds by default |
| Session data | Energy, cost, durations, recovered range, start/end timestamps when provided |
| Authentication | Hager login with OAuth 2.0 / PKCE; automatic token renewal |
| Configuration | Home Assistant UI; English and French translations |
| Diagnostics | Event code, status transitions, redacted diagnostic download |

## Before you install

- Home Assistant **2026.10.0 or later**.
- A cloud-connected Witty Start already visible and controllable in the Hager Witty app, and the corresponding Hager account.
- Internet access from Home Assistant to Hager's login and API services.
- HACS for managed installation, or access to your Home Assistant configuration folder for manual installation.

**Scope:** one charger returned by the account's device endpoint. Multi-charger accounts and other Witty models are not validated. This release does not change current limits, phases, charging power or charger schedules; it provides no local/OCPP connection or built-in solar-surplus controller. Vehicle battery SOC and instantaneous charging power are not exposed.

## Install with HACS

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=yg-dev-ha&repository=hager-witty-home-assistant&category=integration)

1. In **HACS → Custom repositories**, add `https://github.com/yg-dev-ha/hager-witty-home-assistant` as an **Integration**.
2. Download **Hager Witty Start**, then restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Hager Witty Start**.

### Manual installation

Download `hager-witty-v0.1.0.zip` from [Releases](https://github.com/yg-dev-ha/hager-witty-home-assistant/releases). Extract its `custom_components/hager_witty` folder into your Home Assistant configuration directory. The final path must be `/config/custom_components/hager_witty/manifest.json`. Restart Home Assistant and add the integration.

If migrating an existing manual installation to HACS, back up the folder first, install through HACS and restart. Keep the existing configuration entry; the integration domain and entity unique IDs are preserved. Do not nest a second `hager_witty` directory inside the first.

## Connect your account

1. Select your Hager account country and login language (`FR` / `fr` by default).
2. Open the displayed **Hager login** link in a separate browser tab and sign in on Hager's page.
3. The final redirect uses `com.miaaguardusercontent…:/callback`. A desktop browser may report that it cannot open this application link.
4. Copy the **complete callback URI** and paste it into Home Assistant. Alternatively, paste only the value between `code=` and the next `&`.

The full callback is preferred: the integration validates its destination and OAuth `state`. A raw code is supported with PKCE, but cannot carry a state check. Use the code from this setup attempt, once only. If your browser hides the redirect, open its Developer Tools → Network, enable Preserve log and inspect the final redirect's `Location` header. Do not share that URL or a network capture.

If the code expires, reopen the login link and sign in again. If device discovery temporarily fails **after** the code exchange, submit the form again: the active setup flow retains the tokens for that retry. No Hager password is stored by the integration.

## Entities and state

| Entity | Behavior |
|---|---|
| **Charge** switch | ON for confirmed charging; OFF for a connected, idle vehicle; unavailable when unplugged or the status is unknown |
| **Charging** binary sensor | True / false for known codes; **unknown** for unclassified codes |
| **Status / Event code** | Hager description, raw code and event attributes |
| **Session energy** | Session value in kWh; not a lifetime meter for the Energy dashboard |
| **Session cost** | Hager's raw cost, labeled with HA's configured currency; no conversion — check that your account uses the same currency |
| **Connected / Charging duration** | Raw duration values supplied by Hager |
| **Recovered range** | Hager's estimate in km |
| **Session start / end** | Cloud timestamps; missing or timezone-less values remain unknown |
| **Token expiry** | Diagnostic sensor, disabled by default |

The state follows Hager's next reported status; accepting a command does not prove the vehicle has started or stopped. A timeout can leave the outcome uncertain: check the charger/app before retrying. Cloud controls are not an emergency stop.

### Validated event codes

| `StatusEvent.Type` | Observed description | Meaning |
|---:|---|---|
| 2006 | Borne disponible | Unplugged |
| 2007 | Véhicule disponible | Connected, not charging |
| 2009 | Véhicule en charge | Charging |

An open session (`EndDate = null`) is **not** evidence of charging. Unknown codes are logged without guessing their meaning. A mismatched charger ID makes the integration unavailable instead of attributing another charger's readings to the configured device.

## Updates and troubleshooting

The polling interval is configurable from **2 to 300 seconds** in integration options (default **10 s**). Two seconds is for short diagnostic sessions; it cannot overcome Hager's own cloud update delays. HACS offers published releases; apply an update and restart Home Assistant.

| Symptom | What to check |
|---|---|
| Integration unavailable | Hager app/cloud availability, then HA logs; polling retries automatically |
| Charge switch unavailable | Vehicle connection and Event code; unknown states deliberately disable control |
| Reauthentication requested | Complete Hager login again; the refresh token was rejected or is missing |
| Persistent API 401/403 | One token refresh and one retry are attempted; continued API rejection is reported without repeatedly asking for login |
| Unknown event code | Use the dedicated [status-code issue form](https://github.com/yg-dev-ha/hager-witty-home-assistant/issues/new/choose) with the observed physical state |

Enable temporary debug logging from the integration menu when needed. Status transitions are logged at INFO and unknown codes at WARNING. Diagnostics redact tokens, device IDs and names, and exclude the account profile. Review logs and diagnostic descriptions before sharing; free-text cloud messages may contain contextual information.

## Privacy and project status

Tokens are stored in Home Assistant's configuration entry and rotated refresh tokens are persisted. Protect your HA configuration and backups. HTTP error bodies are excluded from integration error messages. The bundled Hager application identifiers/API subscription key come from the mobile-client protocol; they are not a personal developer API key and may change upstream.

This first release is based on observations from a Witty Start. Offline regression tests cover OAuth parsing, refresh/retry behavior and observed status handling. GitHub runs these tests plus HACS and Hassfest validation; these checks do not replace testing on your charger or certify every Hager account/region.

See [Changelog](CHANGELOG.md), [Contributing](CONTRIBUTING.md) and [MIT license](LICENSE). Hager and Witty are trademarks of their respective owner.
