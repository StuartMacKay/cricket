# Cricket — Agent Guide

This file is for AI coding agents. It describes the project's purpose,
architecture, conventions, and design preferences so agents can make good
decisions without rediscovering them from the code.

---

## What Cricket Is

Cricket is a web quality auditing server. It crawls one or more sites on a
cron schedule, runs a set of audits against each page, stores the results
in a database, and exposes everything through an agent-native REST API.

The intended consumers of the API are AI agents: agents can query audit
results, compare metrics over time, identify regressions, and generate
pull requests or reports. The API is designed with this in mind — Bearer
auth, cursor pagination, and a machine-readable schema at `/api/docs`.

---

## Architecture

### The unified audits app

All audit data lives in the `audits` Django app. There are no per-tool
apps. The models are:

```
audits.Site           — identity only: name, slug, url, environment
  └── audits.Job      — configuration: which audits, which pages, schedule
        └── audits.Run          — one execution of a Job
              └── audits.Report — one audit result per (Run × Audit × Page)
                    ├── audits.Metric × N  — extracted scalar measurements
                    └── audits.Finding × N — actionable items

audits.Page           — a URL, shared across all Runs for a Site
audits.Audit          — an audit type, backed by a Celery task
audits.Definition     — describes a measurable quantity produced by an Audit
```

### Model responsibilities

**`Site`** — stable identity. Groups Jobs, Pages, and all their audit history
under a slug. Use separate Site records for different environments (local,
staging, production) of the same project so results are not mixed.

**`Audit`** — registered via data migrations. Maps a slug to the Celery task
that performs the audit and writes a Report. Audits available: `lighthouse`,
`page-headers`, `page-weight`. Each has a corresponding report processor in
`apps/audits/reports/`.

**`Job`** — the configuration unit. Selects a Site, a set of Audits (M2M),
the pages to audit (sitemaps or explicit URL list), device emulation, and a
cron schedule. Each execution creates one Run.

- `Job.sitemaps` — newline-separated sitemap URLs to fetch and parse
- `Job.urls` — newline-separated explicit page URLs
- `Job.schedule` — crontab string; empty means manual-only
- `Job.get_pages()` — yields Page objects, creating them if needed
- `Job.clean()` validates that all URLs/sitemaps belong to the Site's domain

**`Run`** — one execution of a Job. Tracks overall status and task counters.
`Run.task_complete()` increments `completed_tasks` and calls `Run.complete()`
when all tasks are done (uses `SELECT FOR UPDATE` to avoid races).

**`Page`** — a URL belonging to a Site. Created by `Job.get_pages()` on first
encounter; reused across all subsequent Runs. `url` is globally unique.

**`Report`** — the raw output of one Audit against one Page in one Run. Holds:
- `data` JSONField — structured output from the audit task
- `json_report` / `html_report` — file fields (Lighthouse only)
- `error` — exception detail if the audit failed

**`Definition`** — describes a measurable quantity (e.g. "Largest Contentful
Paint"). Has a slug, human name, description, weight, and FK to its Audit.
Registered via data migrations — only metrics listed in `Definition` are
extracted from reports. The five weighted Lighthouse Performance definitions
are seeded in `0001_initial.py`.

**`Metric`** — a recorded measurement extracted from a Report. FK to Page
(denormalised for query performance), Report, and Definition. Stores `score`,
`rating` (poor / needs-improvement / good), `value`, `units`, `measured`
(mirrors Run.created). The primary data for trend analysis.

**`Finding`** — an open-ended actionable item. FK to Page and Report. `type`
is a free slug (e.g. `dead-link`, `large-image`) — no pre-defined list.
Findings can be created by audit tasks or uploaded via the API by agents.

### Task architecture

```
audits.tasks.dispatch_run(job_id)     — creates Run, calls get_pages(), counts
                                         tasks, dispatches one audit_page task
                                         per (Audit × Page), saves total_tasks
audits.tasks.audit_page(run_id, audit_slug, page_id)
                                      — runs the audit, creates Report, calls
                                         report processor, calls run.task_complete()
audits.tasks.check_scheduled_jobs()   — Celery Beat task (every few minutes);
                                         calls Job.is_overdue() and dispatches
                                         overdue Jobs
```

Report processors live in `apps/audits/reports/` and are named after their
audit slug: `lighthouse.py`, `page_headers.py`, `page_weights.py`.

### Scheduling

A single Celery Beat entry runs `check_scheduled_jobs` every few minutes.
That task loads all enabled Jobs and uses `croniter` against `Job.schedule`
and `Job.executed` to find which are overdue. Overdue Jobs are dispatched.
Jobs with an empty `schedule` are manual-only.

### Task queue

Celery with Redis as broker. Single default queue.

---

## API

Django Ninja (not DRF). Routers in `apps/api/routers/`. Schemas in
`apps/api/schemas.py`. Auth: Bearer token via `apps/api/auth.py`.

```
GET  /api/sites/                                      list sites
GET  /api/sites/{slug}/                               site detail

GET  /api/sites/{slug}/jobs/                          list jobs
GET  /api/sites/{slug}/jobs/{id}/                     job detail

GET  /api/sites/{slug}/runs/                          list runs
GET  /api/sites/{slug}/runs/{id}/                     run detail
GET  /api/sites/{slug}/runs/{id}/reports/             list reports in a run
GET  /api/sites/{slug}/runs/{id}/reports/{id}/        report detail (data + file URLs)
POST /api/sites/{slug}/runs/{id}/reports/{id}/findings/  create a finding

GET  /api/sites/{slug}/pages/                         list pages
GET  /api/sites/{slug}/pages/{id}/                    page detail
GET  /api/sites/{slug}/pages/{id}/metrics/            latest metrics for a page
GET  /api/sites/{slug}/pages/{id}/metrics/history/    metric time series
GET  /api/sites/{slug}/pages/{id}/findings/           findings for a page

GET  /api/sites/{slug}/metrics/                       cross-page metrics for a definition
GET  /api/definitions/                                list metric definitions
GET  /api/definitions/{slug}/                         definition detail
```

All list endpoints use cursor pagination: `?limit=` and `?cursor=`.
Filters documented in the individual router files.

---

## Working with result data

### Report data varies by audit type

Each audit stores different data in `Report.data` and `Report.json_report`:

| Audit | Report.data | File fields |
|---|---|---|
| `lighthouse` | `{}` (empty — data is in the JSON file) | `json_report`, `html_report` |
| `page-headers` | `{status_code, headers: {}, redirect_count, final_url}` | none |
| `page-weight` | `{total_transfer_size, total_resource_size, resource_count, by_type: {}}` | none |

Do not process `Report.data` without knowing which audit produced it.

### Metrics

Metrics are extracted from Reports by the report processor and stored in
`Metric` records for trend analysis. Each `Metric` has a `Definition` that
describes what was measured. Discover available Definitions via `GET /api/definitions/`.

Only Definitions registered in the database are extracted. The processor loads
all `Definition` rows for the current audit and skips any metric the report
contains that has no matching Definition. Lighthouse Definition slugs are the
Lighthouse audit IDs directly (e.g. `largest-contentful-paint`).

### Findings

Findings are open-ended. The `type` field is a free slug. Standard types
created by the application's own processors are documented in the processor
source. External agents can upload findings via `POST /runs/{id}/reports/{id}/findings/`
after secondary processing. The `source` field records who created the finding.

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

- `created` / `modified` timestamps on all models (auto_now_add / auto_now).
- Run status: `running / complete / failed`.
- Metric `rating`: `poor / needs-improvement / good`.
- Finding `severity`: `error / warning / info`.
- Sensitive or large raw data (Lighthouse JSON) stored in files (`FileField`),
  not in the database; `Report.data` holds structured summaries only.

### Admin interface

All models registered in Django admin. Data is immutable after collection;
admin is read-only for Reports, Metrics, and Findings. Trigger actions belong
on the Job or Site admin.

### Settings and environment

- `DJANGO_ENV`: `development` or `production`.
- `Site.environment`: `local`, `staging`, `production` — tag each Site with
  the environment it represents. Filter metrics by environment when comparing;
  Lighthouse scores from a local machine and from staging are not comparable.

---

## What to Read First

| File | Why |
|---|---|
| `apps/audits/models/` | All data models — start here |
| `apps/audits/tasks.py` | How Jobs are dispatched and runs completed |
| `apps/audits/reports/lighthouse.py` | Reference report processor |
| `apps/api/routers/pages.py` | Reference for API router patterns |
| `apps/api/schemas.py` | All API response shapes |
| `docs/development-plan.md` | Full roadmap — what is yet to be built |
| `docs/decisions.md` | Decision log — what changed and why |
