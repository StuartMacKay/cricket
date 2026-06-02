# Decision Log

A running record of significant changes to the project and why they were made.
Not exhaustive — the bar is "would a future developer or agent look at this and
wonder why?" If yes, log it. If it's obvious from the code, skip it.

---

## 2026-06-02

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
