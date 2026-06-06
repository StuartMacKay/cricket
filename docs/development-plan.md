# Cricket — Development Plan

This document captures all planned refinements, features, and future ideas in one place.
Its purpose is to prevent good ideas from being lost while keeping day-to-day work
focused. Nothing here is committed to or scheduled; it is a reference for prioritisation
discussions.

---

## Architectural decisions

The reasoning behind architectural choices is in `docs/decisions.md`.
Read that before proposing structural changes.

The current model structure and API are documented in `AGENTS.md`.

---

## Current architecture summary

Cricket uses a single unified `audits` app. New audit types are added by:

1. Creating an `Audit` record (via data migration) with a slug and Celery task path.
2. Writing a Celery task that receives `(run_id, audit_slug, page_id)`, performs the
   audit, creates a `Report`, and calls `run.task_complete()`.
3. Writing a report processor in `apps/audits/reports/<name>.py` that extracts
   `Metric` records from the raw report data.

No new Django app is required for a new audit type. The admin, API, and scheduling
infrastructure are shared.

---

## Scheduling

A single Celery Beat entry runs `check_scheduled_jobs` every few minutes:

```python
app.conf.beat_schedule = {
    "check-overdue-jobs": {
        "task": "audits.tasks.check_scheduled_jobs",
        "schedule": crontab(minute="*/5"),
    },
}
```

`check_scheduled_jobs` queries all enabled Jobs and uses `croniter` against
`Job.schedule` and `Job.executed` to find which are overdue. Overdue Jobs are
dispatched via `audits.tasks.dispatch_run`. Jobs with an empty `schedule` are
manual-only.

---

## Stage 0 — Foundation ✓

Implemented. SQLite, Celery task architecture, basic admin, API auth.

---

## Stage 1 — Environment tagging and per-tool enable flags ✓

Implemented (differently than planned). `Site.environment` tags a site's environment.
Separate `Site` records replace the old enable flags — if a Job exists for an audit
type on a given Site, that audit runs.

---

## Stage A — Architectural refactoring ✓

Implemented as a unified `audits` app rather than as per-tool apps. See
`docs/decisions.md` (2026-06-06 entry) for the full rationale and what changed.

---

## Stage 2 — Django Debug Toolbar integration

*Depends on Stage A ✓. Full design in `docs/ddt-integration-plan.md`.*

DDT slots in as a new audit type in the unified model. The companion package
(`django-cricket`) is still required in the target application.

**What needs to be built:**

- **Two new `Audit` records** (via data migration): `ddt-sql` and `ddt-cache`.
  Each maps to its own Celery task. `Job.audits` M2M selects which panels to collect,
  replacing the old per-panel boolean fields on `debugtoolbar.Job`.

- **`audits.tasks.audit_ddt_page(run_id, audit_slug, page_id)`** — makes two HTTP
  requests (target page → get store_id; companion endpoint → get panel JSON), creates
  a `Report` with raw panel data in `data`, extracts scalar `Metric` records, calls
  `run.task_complete()`. Reads `cricket_secret` from `Job.config["cricket_secret"]`
  (see "Per-job audit config" below).

- **`apps/audits/reports/ddt.py`** — report processor. Extracts scalar metrics:
  `sql-query-count`, `sql-total-time-ms`, `sql-duplicate-count`, `cache-calls`,
  `cache-hits`, `cache-misses`. Definition records upserted on first run.

- **`apps/DDT_COLLECTION_ENABLED`** guard — the task raises a non-retrying exception
  when `settings.DDT_COLLECTION_ENABLED` is False, producing a failed Report with a
  clear message.

- **`management/commands/prune_old_ddt_reports.py`** — deletes `Report.data` on DDT
  reports older than N days, preserving the Metric records.

- **Companion package `django-cricket`** — separate repository, published to PyPI.
  See `docs/ddt-integration-plan.md` for the specification.

**Per-job audit config:**

Some audits need per-job configuration that doesn't fit the common `Job` fields
(e.g. `cricket_secret` for DDT). The resolution: add `config = JSONField(null=True,
blank=True)` to `Job`. Audits that need per-job config read from
`job.config.get("cricket_secret", "")`. The field is an escape hatch — most audits
ignore it. The admin renders it as a raw JSON editor for operators.

**Data storage:**

| What | Where |
|---|---|
| Raw panel JSON | `Report.data` JSONField, pruned after 90 days |
| `sql-query-count`, `cache-hits`, etc. | `Metric` records — kept long-term |
| Definitions for DDT metrics | `Definition` records, upserted at first run |

**Settings:**
```python
DDT_COLLECTION_ENABLED = DJANGO_ENV == "development" and DEBUG
```

---

## Stage 3 — Multi-instance sync (local → shared server)

*Depends on Stage 2.*

A local cricket instance collects DDT data and pushes it to a shared team server.
Only environment-independent data (SQL counts, cache stats) is worth pushing — these
live in `Metric` records. Lighthouse and pageweight results are not pushed.

The `Site.environment` field on the *source* `Job`'s site is preserved on the remote
to maintain provenance.

- **Push endpoint**: `POST /api/sites/{slug}/runs/{run_id}/push/` (admin key required).
  Serialises the Run, its Reports (data field and Metrics), and Pages, then creates
  corresponding records on the remote. File fields are omitted (null on the remote).

- **`push_run` management command**: `--run-id <id> --remote <url> --key <token>`.
  Requires explicit arguments to prevent accidental pushes.

- Agents query the shared server with `GET /api/sites/{slug}/metrics/?audit=ddt-sql`
  to see pushed DDT scalar data.

---

## Stage 4 — JS and CSS coverage

*Depends on Stage 2 (same Puppeteer session as page-weight). New audit type.*

Chrome DevTools Protocol Coverage API, sharing the page-weight Puppeteer session.

- New `Audit` record: `js-coverage`, `css-coverage`.
- `Report.data` stores per-script/stylesheet used/unused byte counts.
- `Metric` records for aggregate coverage percentage per page.
- Key limitation: interaction-triggered code appears unused. Frame as "not executed
  during page load."

---

## Stage 5 — Cold/warm cache comparison

*Depends on Stage 4. Extends the page-weight audit.*

Second Puppeteer pass in the same collection task — warm cache results stored
as additional `Metric` records alongside the cold-cache metrics.

Definitions: `page-weight-warm`, `cache-saving-bytes`, `cache-saving-pct`.

---

## Stage 6 — HTML validation

*New audit type following the page-headers pattern.*

W3C Nu Html Checker JSON API, one POST per page.

- New `Audit` record: `html-validation`.
- `Report.data` stores the full message list: `[{message, type, line, column}]`.
- `Metric` records: `html-error-count`, `html-warning-count`.
- `Finding` records created for each validation error/warning with `type="html-error"`.

---

## Stage 7 — Broken link detection

*New audit type following the page-headers pattern.*

Per-page link extraction and HEAD request checking.

- New `Audit` record: `link-check`.
- `Report.data` stores the full link list: `[{url, status_code, source_url}]`.
- `Metric` records: `broken-link-count`, `redirect-link-count`.
- `Finding` records created for each broken link with `type="broken-link"`.

Note: broken links are a natural fit for Findings (open-ended actionable items)
and the `POST /runs/{id}/reports/{id}/findings/` endpoint means an external
link-checker agent could populate them without a built-in audit task.

---

## Future ideas (no stage assigned)

**Webhook notification on run completion**
Useful for notifying an agent that a requested run has finished, avoiding polling.
Deferred until real agent usage clarifies what works best — the right model (URL on
the Job vs. per-trigger POST body) isn't obvious without experience.

**Agent-triggered runs**
`POST /api/sites/{slug}/runs/` to dispatch a run on demand. Currently runs are only
triggered by the scheduler or admin. Useful for agents that want to request a fresh
audit before analysing results.

**Per-Job rate limiting**
An optional `delay_between_pages` or `concurrency` field on `Job` to control request
rate to the target site. Worker concurrency is the current blunt instrument. Defer
until real-world usage shows whether per-Job control is needed.

**Run and Metric record pruning**
Management commands to delete old Runs (and their Reports and Findings) beyond a
configurable retention period, while optionally preserving Metric records for
long-term trend analysis. Defer until usage patterns clarify how much history is useful.

**Carbon footprint estimate**
Derived from page-weight transfer size via the Website Carbon API. A computed Metric
at report-processing time, no new collection needed.

**DNS and TLS analysis**
Per-domain rather than per-page. Overlaps with headers data. Revisit when security
auditing requirements are clearer.

**First-party vs third-party resource breakdown**
Derivable from page-weight `Report.data` at query time. Could be exposed as derived
Metrics or as a summary API endpoint. Not a new collection task.

**Structured data validation**
Schema.org / Open Graph tag validation. Lighthouse covers some of this already.
Would fit as a Finding type rather than a Metric.
