# Changelog

## Unreleased

- Renamed project from **django-lighthouse** to **Cricket**.
- Added `headers` app: HTTP response header auditing via `requests`.
- Added `pageweight` app: Puppeteer-based page transfer-size measurement.
- Added `api` app: agent-native REST API built with Django Ninja.
  - Bearer token authentication with per-site API key scoping.
  - Cursor-based pagination on all list endpoints.
  - Async snapshot trigger (202 + poll URL + optional webhook).
  - Machine-readable context document at `GET /api/agent-context/`.
- Promoted `Site.config` JSONField to `platform` (CharField with choices)
  and `extra_config` (JSONField for advanced overrides).
- Upgraded Node.js to 22 LTS and Lighthouse to 13.
- Upgraded Django to 6.0.
