# Cricket — Agent Guide

This file is for AI coding agents. It describes the project's purpose,
architecture, conventions, and design preferences so agents can make good
decisions without rediscovering them from the code.

---

## What Cricket Is

Cricket is a web quality auditing server. It crawls one or more sites on a
cron schedule, runs a set of collectors against each page, stores the results
in a database, and exposes everything through an agent-native REST API.

The intended consumers of the API are AI agents: agents can query audit
results, compare snapshots over time, identify regressions, and generate
pull requests or reports. The API is designed with this in mind — Bearer
auth, cursor pagination, 202 async with poll URLs, and a machine-readable
contract at `GET /api/agent-context/`.

---

## Architecture

### The collector pattern

Every audit type is a separate Django app. Each follows an identical structure:

```
sites.Site
  └── sites.Scan            (one per audit run — status, environment, timestamps)
        ├── sites.Page × N  (shared URL list — one record per URL per scan)
        ├── lighthouse.Run  (status, config — no pages of its own)
        ├── headers.Run     (status)
        ├── pageweight.Run  (status)
        └── debugtoolbar.Run (status)
```

Tool-specific results reference `sites.Page` directly:

```
lighthouse.PageAudit  → FK(sites.Page)
headers.PageData      → FK(sites.Page)
pageweight.PageData   → FK(sites.Page)
debugtoolbar.PageData → FK(sites.Page)
```

Each `Run` is dispatched in parallel via Celery when a `sites.Scan` is created.
Each uses a Celery chord: a group of per-page tasks → a completion aggregator that
sets `status=COMPLETE` and `page_count` on the `Run`, then signals the parent `Scan`.

The `headers` app is the simplest reference implementation for new collectors.

The reasoning behind these structural choices is in `docs/decisions.md`.

### Per-tool enable flags

`sites.Site` has a boolean flag for each collector: `enable_lighthouse`,
`enable_headers`, `enable_pageweight`, `enable_toolbar`. `take_site_scan` checks
each before dispatching. Default `True` for all except `enable_toolbar`.

Different collection cadences use separate `Site` objects with different crontabs
and different flags — not per-tool schedules on one Site.

### Environment tagging

`sites.Scan` has an `environment` field (`local`, `staging`, `production`).
Always filter scan queries by environment when comparing metrics. Page weight and
Lighthouse scores from a local machine are not comparable to those from staging.
DDT SQL query counts are environment-independent and can be collected locally then
pushed to a shared server.

### Task queue

Celery with Redis as broker. Two queues:
- `sites` — high priority, orchestration tasks
- `pages` — default, per-page measurement tasks

Celery Beat triggers `sites.tasks.take_snapshots` every hour.

### API layer

Django Ninja (not DRF). Routers live in `apps/api/routers/`. Schemas in
`apps/api/schemas.py`. Authentication is Bearer token via `apps/api/auth.py`.

```
/api/sites/{slug}/scans/                        list / trigger
/api/sites/{slug}/scans/{id}/                   scan detail
/api/sites/{slug}/scans/{id}/pages/             shared page list (all tools)
/api/sites/{slug}/scans/{id}/pages/{page_id}/   page detail
/api/sites/{slug}/scans/{id}/{tool}/pages/      tool-specific page results
/api/sites/{slug}/scans/{id}/{tool}/pages/{id}/ tool-specific page detail
```

---

## Working with result data

### JSONField structures vary by tool

Each tool's detail fields have a specific structure. Do not attempt to process
a JSONField without knowing which tool produced it. The `agent-context` endpoint
documents the structure for each tool. Reference shapes:

| Tool / field | Structure |
|---|---|
| Lighthouse `PageAudit.details` | `[{url, totalBytes, wastedMs}]` (failing items) |
| DDT `Page.sql_queries` | `[{sql, time_ms, traceback}]` |
| HTML validation errors | `[{message, type, line, column}]` |
| Broken link list | `[{url, status_code, source_url}]` |
| JS coverage functions | `[{name, executed, script_url}]` |

### Lighthouse audit IDs are cricket-owned stable slugs

Cricket maps Lighthouse's internal audit IDs to stable slugs before storing them.
Lighthouse has changed internal IDs across versions; cricket's slugs do not change.
Discover audit IDs via `GET /api/audits/` rather than hardcoding them.

### Snapshot aggregation

Pre-aggregated summary tables (`SnapshotCategory`, `SnapshotAudit`) have been
removed. The API computes summaries on demand. Per-page results are the source
of truth — query and aggregate them directly.

---

## Design Preferences

### Documentation pattern

Three documents, three jobs:
- **`AGENTS.md`** (this file) — current state. What the project is right now.
- **`docs/development-plan.md`** — what is yet to be built, in order.
- **`docs/decisions.md`** — what changed and why, in chronological order.

When a significant architectural decision is made, append an entry to
`docs/decisions.md` before moving on. When a stage is implemented, update
`AGENTS.md` to reflect the new current state and remove it from the plan.

### Always use structured JSON

**Agents need structured JSON to have the greatest freedom when analysing results
or generating reports.** Never design a collector or endpoint that returns HTML or
data that requires parsing. If there is a choice between scraping display-oriented
output and writing code to produce clean JSON, always choose JSON.

### Data model conventions

- All models inherit `TimeStampedModel` (adds `created`, `modified`).
- Scan/Run status: `pending / running / complete / failed`.
- Sensitive or large raw data (SQL text, stack traces, raw Lighthouse JSON) is
  stored separately from summary scalars and pruned on a shorter schedule.
  Summary scalars are kept for long-term trend analysis (1 year default).

### Admin interface

All Snapshot and Page models are registered read-only. Data is immutable after
collection. Trigger actions belong on the `Site` admin via Django admin actions.

### Settings and environment

- `DJANGO_ENV`: `development` or `production`.
- Feature flags that gate collection live in `config/settings.py`.
- Per-site overrides (Lighthouse CLI flags, companion middleware secrets, etc.)
  live in `Site.extra_config` (JSONField).

---

## Planned Work

Full details in `docs/development-plan.md`.

| Stage | Work |
|---|---|
| 0 | Foundation: rename Snapshot→Scan, introduce sites.Page, remove pre-aggregation, stable Lighthouse IDs, tests, deployment |
| 1 | Per-tool enable flags on Site; environment field on Scan |
| 2 | DDT integration (new `debugtoolbar` app) |
| 3 | Multi-instance sync (push selected tools local → shared server) |
| 4 | JS/CSS coverage (extends pageweight app) |
| 5 | Cold/warm cache comparison (extends pageweight app) |
| 6 | HTML validation (new app) |
| 7 | Broken link detection (new app) |

---

## What to Read First

| File | Why |
|---|---|
| `apps/headers/` | Simplest collector — the reference pattern for new collectors |
| `apps/sites/tasks.py` | Where all collectors are dispatched |
| `apps/api/routers/pages.py` | Reference for a collector API router |
| `apps/api/routers/introspection.py` | The agent-context endpoint |
| `config/settings.py` | Environment gating and feature flags |
| `docs/development-plan.md` | Full roadmap — what is yet to be built |
| `docs/decisions.md` | Decision log — what changed and why |
| `docs/ddt-integration-plan.md` | Detailed design for the DDT collector (terminology partially stale — see note at top) |
