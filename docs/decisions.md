# Decision Log

A running record of significant changes to the project and why they were made.
Not exhaustive — the bar is "would a future developer or agent look at this and
wonder why?" If yes, log it. If it's obvious from the code, skip it.

---

## 2026-06-02

### Scheduling via a single master check task

Rather than managing PeriodicTask database records for each Job or maintaining a
static beat schedule that must be updated whenever a Job is added or changed, a single
Celery Beat entry runs a check task every few minutes. That task loads all enabled Jobs
and uses `croniter` against `Job.crontab` and `Job.last_run` to determine which are
overdue. Overdue Jobs are dispatched. This is the same pattern used by
`Site.objects.overdue()` in the current codebase.

The approach is simple to reason about, requires no dynamic schedule management, and
works well for the typical usage pattern where Jobs run at well-defined intervals (first
of the month, Monday mornings). A Job with an empty crontab is manual-only.

### Boolean fields for tool-specific selectors

Per-tool Job models use separate boolean fields for selectors rather than a
MultiSelectField (which requires a third-party package and stores as a comma-separated
string) or a JSONField. One boolean per Lighthouse category, one per DDT panel. This
renders as checkboxes in the admin, filters directly in the ORM
(`job__cat_performance=True`), and requires no extra dependencies. The same pattern
applies to any future tool that has a fixed, small set of selectable options.

### url_list as a first-class URL source

`url_list` is added as a built-in `url_source` option alongside `sitemap_url` and
`sitemap_file`. A newline-separated list of URLs in `url_value` covers the common
case of a small, hand-curated set of pages without needing a sitemap. A custom
sitemap (sitemap_file) remains the right approach for editing a subset of an existing
sitemap.

### Per-tool Job models with typed configuration fields

A generic `sites.Job` with `config = JSONField` for collector-specific settings puts
structure that belongs in the model into a blob. It cannot be validated at the model
level, renders poorly in the admin (raw JSON editor), and makes filtering by
configuration — "which Jobs run performance audits?" — require JSON field lookups.

Each tool's Job model instead carries its configuration as typed fields:
`lighthouse.Job` has `platform` (CharField with choices) and `categories`
(MultiSelectField); `pageweight.Job` has `device`; `debugtoolbar.Job` has `panels`
(MultiSelectField, profiling off by default) and `cricket_secret` (CharField). Common
fields (site FK, url_source, url_value, environment, crontab, enabled) live in an
abstract `BaseJob`. Tool-specific config is translated to the tool's native format at
dispatch time — Lighthouse CLI flags, DDT companion endpoint query parameters, etc.

This applies consistently to the API: per-tool job endpoints expose typed fields
directly, so an agent can filter `?categories=performance` without parsing JSON.

Each tool app is fully self-contained: Job model, Run model, Page model, tasks, admin,
and API router. The `api` app assembles routers with one line per tool. Adding a new
collector adds one app and one registration.

### Toolbox architecture: Job replaces Site as configuration unit

The current `Site` model conflates two responsibilities: **identity** (a stable name
agents and humans use to refer to a site) and **configuration** (what URLs to audit,
which tools to run, on what schedule). Separating these is the key structural change
in Stage A.

`sites.Job` becomes the configuration unit: one collector, one URL source, one
schedule. `sites.Site` becomes identity only: name, slug, primary_url, description.
The `environment` field moves from `Scan` to `Job` — a Job configured to run locally
is always a local Job.

Collectors are independent. Each Job's Run completes on its own without coordination.
The URL string is the join key across tools and across time; no shared page list or
parent Scan record is needed. An agent wanting a cross-tool picture of a page queries
each tool's run list for that URL.

This removes `sites.Scan`, `sites.Page`, `signal_scan_complete`, and all enable flags
on `Site`. A collector is enabled for a site by the existence of a Job for it.

**Why not a Project model for multi-tenancy?** Isolation between teams is better
handled by running separate cricket servers. Within a server, different teams (e.g.
dev and support) typically need access to the same data. No permission modelling in
the application is needed; API key scoping to a Site is sufficient for agent access
control.

---

## 2026-06-06

### Per-tool apps replaced by a single unified `audits` app

The previous architecture had four separate Django apps for data storage:
`sites`, `lighthouse`, `headers`, and `pageweight`. Each tool app had its
own `Job`, `Run`, and `Page` models that duplicated common structure (site FK,
status, crontab scheduling, URL discovery). Tool-specific results were stored
in tool-specific models (`lighthouse.PageAudit`, `headers.Page`,
`pageweight.Page`) with no shared abstraction for the concept of a metric or
a measurement.

All four apps have been deleted and replaced by a single `audits` app with
the following models:

- **`Site`** — identity only (name, slug, url, environment). Moved
  `environment` from `Scan` to `Site`; separate Site records replace the old
  per-tool enable flags as the mechanism for controlling what runs and where.

- **`Audit`** — replaces the implicit concept of a tool. Each `Audit` record
  maps a slug to the Celery task that performs the work. Registered via data
  migrations. Agents can discover available audits via `GET /api/definitions/`.

- **`Job`** — replaces `sites.BaseJob` and all per-tool job subclasses
  (`lighthouse.Job`, `headers.Job`, `pageweight.Job`). One Job record covers
  any combination of Audits via an M2M relationship. Per-tool typed config
  fields (Lighthouse `platform`, `cat_performance`, etc.) are not replicated;
  the current audits are configured at the Audit/task level instead.

- **`Run`** — replaces the per-tool run models. Tracks `total_tasks` and
  `completed_tasks` counters; `task_complete()` marks the Run complete when
  all audit-page tasks finish, using `SELECT FOR UPDATE` to avoid races.
  No separate Scan coordinator model is needed.

- **`Page`** — replaces both `sites.Page` (which was per-scan) and the
  per-tool page models (`lighthouse.Page`, `headers.Page`, `pageweight.Page`).
  A `Page` is now a stable identity record for a URL within a Site, reused
  across all Runs. `url` is globally unique (not unique-per-scan), so Reports
  from different Runs can be compared by URL without joining through a scan.

- **`Report`** — the raw output of one Audit against one Page in one Run.
  Replaces `lighthouse.PageAudit` (which also embedded metric extraction),
  `headers.Page` (which stored results directly on the page model), and
  `pageweight.Page`. Stores `data` as a JSONField plus optional file fields
  for Lighthouse's JSON/HTML reports.

- **`Definition`** — replaces `lighthouse.AuditDefinition`. Generalised to
  cover any audit, not just Lighthouse. Renamed from `Metric` (the original
  name for the description of a measurable quantity) to `Definition` to
  avoid confusion with recorded measurements.

- **`Metric`** — replaces `lighthouse.PageAudit` (scalar fields) and the old
  `Value` model (which was itself renamed from `Metric`). Stores one recorded
  measurement per (Report, Definition) pair. Denormalises `page` and `measured`
  for query performance. Supports `score`, `rating`, `value`, `units`.

- **`Finding`** — new model with no predecessor. Open-ended actionable items
  (dead links, oversized images, etc.) attached to a Report and Page. The
  `type` field is a free slug rather than a FK to a pre-defined table, so new
  finding categories require no migrations. Findings can be created by audit
  tasks or uploaded via the API by external agents.

**What drove the consolidation:**

The per-tool app structure was designed for a world where each collector was
entirely independent. In practice, the common structure (Job scheduling, Run
tracking, Page URL management, metric storage) was being duplicated across
every tool. Adding a new collector meant copying the same scaffolding. The
unified model makes the collector pattern explicit at the model level: each
Audit is a named capability backed by a Celery task, and all results flow
through the same Report → Metric / Finding pipeline.

**What stayed the same:**

The report processors in `apps/audits/reports/` contain the tool-specific
logic that was previously embedded in per-tool Page models (`page.audit()`,
`page.fetch()`, `page.measure()`). The Celery task structure (one
`audit_page` task per page per audit) is unchanged.

---

### Model naming: Definition and Metric

During the unification, the names `Metric` and `Definition` were swapped from
their original assignments:

- Old `Metric` (description of a measurable quantity) → **`Definition`**
- Old `Value` (a recorded measurement) → **`Metric`**

`Definition` better describes something that defines what is measured.
`Metric` better describes the actual recorded data point. The old names were
inherited from the Lighthouse-only era and were confusing in a generalised
context.

---

### API redesigned around unified resources

The old API had per-tool routers under paths like `/api/sites/{slug}/lighthouse/`
with an auto-discovery mechanism (`AGENT_CONTEXT` dicts in each tool's `api.py`
and an introspection endpoint that assembled them). The new API has a single
flat set of routers covering all tools uniformly:

```
/api/sites/{slug}/jobs/
/api/sites/{slug}/runs/{id}/reports/{id}/
/api/sites/{slug}/pages/{id}/metrics/history/
/api/sites/{slug}/pages/{id}/findings/
/api/definitions/
```

Agents filter by `?audit=` to narrow results to a specific tool rather than
routing to a tool-specific endpoint. This removes the need for the
introspection auto-discovery mechanism entirely.

---

## 2026-05-30

### Structured JSON as the primary output format

Cricket is agent-first. Agents need structured data to have the greatest freedom
when analysing results, generating reports, or creating pull requests. Any
temptation to scrape or parse display-formatted output (e.g. HTML from a
third-party tool) should be resisted in favour of writing a small amount of code
to produce clean JSON. This drove the choice of companion middleware for DDT
(below) over parsing DDT's render_panel HTML endpoint.

### Django Debug Toolbar data collected via companion middleware

Two approaches were evaluated for collecting DDT panel data. The first: make a
request to the page, extract the store_id from the response, then call DDT's
existing `/__debug__/render_panel/` endpoint for each panel. This requires no
changes to the target app but returns HTML designed for display — it truncates
output and its structure changes between DDT versions.

The second: install a thin companion package (`django-cricket`) in the target
app that exposes panel data as structured JSON via `/__cricket__/toolbar/`.
Chosen for the reasons above. The package is a separate repository published
to PyPI. Full design in `docs/ddt-integration-plan.md`.

### Per-tool app structure retained over a unified audit model

A unified model was evaluated where all audit results (Lighthouse, headers,
pageweight, DDT) would share one set of tables. Rejected because agents are
domain-specific — an agent diagnosing N+1 SQL queries never needs Lighthouse
data; an agent auditing SEO never needs SQL counts. Separate endpoint groups per
tool are a feature, not a deficiency.

---

## 2026-06-01

### Stage 0 and Stage 1 model changes applied

All model changes from Stage 0 and Stage 1 of the development plan are implemented in the initial migrations; no incremental migrations exist.

**Rename Snapshot → Scan / Snapshot → Run:** `sites.Snapshot` → `sites.Scan`; per-tool `Snapshot` models → `Run` (lighthouse, headers, pageweight). Reflects that cricket actively scans sites rather than passively snapshotting them. All related names, admin classes, task names, and API URLs updated accordingly. API moves from `/snapshots/` to `/scans/`.

**Shared page list via sites.Page:** `sites.Page(scan, url)` replaces three separate per-tool page models (`lighthouse.Page`, `headers.Page`, `pageweight.Page`). Pages are created once by `take_site_scan` before tool tasks are dispatched. All per-tool result models reference `sites.Page` via FK.

**lighthouse.Page split into PageResult + PageCategory + PageAudit:** The old `lighthouse.Page` held both the URL (now in `sites.Page`) and audit results. Audit results (PageCategory, PageAudit) now FK to `sites.Page`. Report files and the `audited` flag move to `lighthouse.PageResult` (OneToOneField on `sites.Page`).

**Pre-aggregation removed:** `SnapshotCategory` and `SnapshotAudit` and the `collect_metrics()` aggregation step are deleted. The API computes category summaries on demand from `PageCategory`. `lighthouse.Run.complete()` replaces the completion-signalling half of the old `collect_metrics()`.

**pageweight.Resource.page re-pointed:** `Resource.page` FK moves from `pageweight.Page` to `sites.Page`, consistent with all other per-tool result models.

**Stage 1 — per-tool enable flags:** `Site.enable_lighthouse`, `enable_headers`, `enable_pageweight`, `enable_toolbar` (defaults True/True/True/False). `take_site_scan` dispatches only enabled tools.

**Stage 1 — environment field on Scan:** `Scan.environment` CharField populated from `Site.extra_config["environment"]` at scan creation. API exposes `?environment=` filter on the scans list endpoint.

---

## 2026-05-31

### Snapshot renamed to Scan

"Snapshot" implies a passive copy of the site was taken. "Scan" describes the
process accurately — the site was actively scanned by one or more tools. The
rename affects models, tasks, API endpoints, and documentation throughout.
`sites.Snapshot` → `sites.Scan`, `lighthouse.Snapshot` → `lighthouse.Run`,
and so on for all tool-level child models.

### Shared URL list via sites.Page

Each tool previously maintained its own Page model (lighthouse.Page,
headers.Page, pageweight.Page) containing duplicate lists of the same URLs.
A shared `sites.Page` model, owned by `sites.Scan`, replaces all three. All
tool-specific result models reference `sites.Page` via FK. The per-tool Page
models are removed. The question "which URLs were included in this scan?" now
has one authoritative answer.

### Pre-aggregation removed (collect_metrics)

`collect_metrics()` on `lighthouse.Snapshot` did two things: pre-aggregated
per-page results into `SnapshotCategory` and `SnapshotAudit` summary tables,
and handled completion signalling. The pre-aggregation was built for a PDF
report use case. On-demand aggregation with proper database indexing is fast
enough for any realistic snapshot size. The summary models and population code
are removed. Completion signalling moves into each Run's completion task.

### Environment tagging on Scan

Cricket supports a workflow where a local instance collects DDT data and pushes
it to a shared team server that also receives data from staging. Without tagging,
page weight figures from a developer laptop and from a staging server would sit
in the same list with no indication they are incomparable. An `environment` field
on `sites.Scan` (populated from `Site.extra_config["environment"]`) makes
provenance explicit. The API exposes `?environment=` as a filter.

### Worker count controls both database concurrency and request rate

The number of concurrent database writes equals the number of Celery workers — no
more, no less. This makes worker count a single lever with two desirable effects:
keeping it low protects SQLite from write contention, and keeping it low also
throttles the rate of HTTP requests to the target site, avoiding excessive load or
being blocked.

The practical consequence is that worker count should be configurable per deployment
context rather than fixed. A local development server can be hammered with many
workers for fast scans. A production or staging site warrants a low worker count to
remain polite. This can be controlled via the `--concurrency` flag when starting the
worker, or via an environment variable, without any code changes.

### Multiple Site objects for different collection cadences

Different tools benefit from different schedules — Lighthouse audits are
expensive and stable (run monthly), page weight is cheap and benefits from
larger sample sizes (run hourly). Rather than adding per-tool scheduling
complexity to a single Site, separate Site objects with different crontabs and
tool enable flags handle this. Some duplication of sitemap configuration is
the trade-off.

### Lighthouse audit IDs mapped to cricket-owned stable slugs

Lighthouse has changed its internal audit IDs across versions (e.g. FID was
replaced by INP). Storing Lighthouse's internal IDs directly means a tool version
update silently breaks any agent or query that references a specific audit ID. The
collection task maps Lighthouse-internal IDs to cricket-owned stable slugs before
storing them. The mapping lives in the collection code, not the database. Agents
discover audit IDs via `GET /api/audits/` rather than hardcoding them.

### SQLite chosen over PostgreSQL

The number of concurrent database writes equals the number of Celery workers
(documented in the worker concurrency decision), making SQLite viable with
controlled worker counts. PostgreSQL was dropped to reduce deployment friction:
no separate database service, no driver dependency, and the database file lives
alongside the application. `psycopg[binary]` removed from `pyproject.toml`;
the Docker Compose stack drops the `postgres` service and uses a named `data`
volume for the SQLite file in production. Development uses the project root so
the file is directly accessible on the host.

### Documentation pattern established

Three documents, three jobs:
- `AGENTS.md` — current state of the project. Always reflects what exists now.
- `docs/development-plan.md` — what is yet to be built, in order. Living document.
- `docs/decisions.md` — this file. What changed and why, in chronological order.
  Append-only; gaps are acceptable; the bar is "would this be confusing without
  an explanation?"
