# Contributing

Report bugs and observed charger states using the issue forms. Include Home Assistant and integration versions, charger model and connectivity, expected behavior and sanitized logs. Do not include OAuth callbacks, tokens, device/account IDs or network captures containing credentials.

Status mappings require observed evidence: event code, cloud description, physical cable/charging state and the preceding command. An open charging session alone does not prove active charging.

## Local checks

Python 3.12+ with `aiohttp` is sufficient for the isolated transport/state tests:

```sh
python -m pip install aiohttp
python -m unittest discover -s tests -v
python -m compileall -q custom_components
python scripts/build_release.py
```

These tests use fake HTTP responses and do not access a Hager account. They do not exercise the complete Home Assistant runtime. GitHub additionally runs HACS and Hassfest; changes to setup and entities should be tested on a development HA instance before release.

## Releases

The initial v0.1.0 is published after all validation jobs succeed on main. Later releases are explicitly requested with the workflow's **publish_release** option after updating `manifest.json`, release notes and documentation. Existing releases are never replaced automatically. The ZIP contains only `custom_components/hager_witty`, README files, changelog and license; HACS installs from the tagged repository.
