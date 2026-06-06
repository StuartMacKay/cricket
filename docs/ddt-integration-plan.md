# Django Debug Toolbar Integration Plan

## Overview

This document describes how to integrate Django Debug Toolbar (DDT) data collection
into cricket as a new audit type. DDT differs from the other audits in two important
ways: it requires a cooperative target application, and its most valuable metrics
(SQL query counts) are environment-independent, making local collection meaningful
on a shared server.

---

## Architecture fit

Under the unified `audits` model, DDT is not a separate Django app — it is a set of
new `Audit` records, each backed by a Celery task and a report processor.

Each DDT panel becomes its own `Audit` so that the `Job.audits` M2M controls which
panels are collected, just as it controls which tool audits run:

```
Audit(slug="ddt-sql")     → task: audits.tasks.audit_ddt_page ("ddt-sql")
Audit(slug="ddt-cache")   → task: audits.tasks.audit_ddt_page ("ddt-cache")
```

A Job that should collect DDT SQL and cache data selects both `ddt-sql` and `ddt-cache`
in its `audits` M2M. A Job that should only collect SQL query counts selects `ddt-sql`
only. No per-panel booleans on the Job model — panel selection is Job configuration.

```
audits.Job (audits=[ddt-sql, ddt-cache, ...])
  └── audits.Run
        └── audits.Report (audit="ddt-sql", page=..., data={raw panel JSON})
              └── audits.Metric (definition="sql-query-count", value=47)
              └── audits.Metric (definition="sql-duplicate-count", value=3)
```

Setting `Site.environment = "local"` on the Site used for DDT Jobs makes provenance
unambiguous. Agents filter by site slug or environment when querying results.

---

## Per-job audit configuration: `Job.config`

Some audits need per-job configuration that doesn't fit the common `Job` fields.
For DDT, the companion endpoint secret (`cricket_secret`) is job-specific — different
deployments use different secrets.

Resolution: add `config = JSONField(null=True, blank=True)` to `Job`. The DDT task
reads `job.config.get("cricket_secret", "")`. Operators set this in the admin.

This field is an escape hatch used only by audits with site-specific secrets or
overrides. Most audits ignore it. It does not replace typed fields for common
configuration (device, schedule, etc.).

---

## Technical challenge: extracting DDT panel data

Django Debug Toolbar stores panel data in Django's cache using a `store_id` generated
per request. The store_id is embedded in the response HTML (as `data-store-id` on the
toolbar container).

### Alternative considered: cookie + `render_panel` endpoint

Using DDT's existing `/__debug__/render_panel/?store_id=<id>&panel_id=<id>` endpoint
requires no changes to the target app but returns HTML formatted for display — not
structured JSON. DDT truncates panel output for display performance; `panel.get_stats()`
server-side returns the full dataset. Panel HTML layouts change between DDT versions.
This approach was rejected as a fragile foundation for automated long-term collection.

It remains viable as a zero-setup prototype to validate that the data is useful before
investing in the companion package.

### Confirmed approach: thin companion middleware (`django-cricket`)

A minimal standalone Django package is installed in the target application.

**Package structure:**
```
django_cricket/
  __init__.py
  apps.py          # AppConfig: name="django_cricket"
  middleware.py    # Captures store_id after DDT processes request
  views.py         # JSON endpoint: GET /__cricket__/toolbar/?store_id=<id>
  urls.py
  serializers.py   # Converts DDT panel.get_stats() → clean JSON dict per panel
```

**The endpoint** (`/__cricket__/toolbar/`):

1. Receives `?store_id=<id>` from cricket's collector task.
2. Looks up the DDT store: `cache.get(f"djdt:{store_id}")`.
3. Calls `panel.get_stats()` on each enabled panel in the stored toolbar.
4. Returns a JSON response mapping panel names to their structured stats.

**Authentication**: Protected by shared secret + `INTERNAL_IPS`. The secret is stored
in `Job.config["cricket_secret"]`. Different Jobs use different secrets, set in the
admin without editing JSON.

**Target app setup:**
```python
# settings.py (development only)
INSTALLED_APPS += ["django_cricket"]
CRICKET_SECRET = env.str("CRICKET_SECRET", default="")

# urls.py
urlpatterns += [path("__cricket__/", include("django_cricket.urls"))]
```

Cricket sends the secret in a request header. Installation: `pip install django-cricket`.

**Panel selection**: The endpoint accepts `?panels=SQLPanel,CachePanel`. The DDT task
derives the panel list from `audit_slug` — `ddt-sql` → `SQLPanel`, `ddt-cache` →
`CachePanel`. A single HTTP request to the companion endpoint can fetch multiple panels
at once; the task batches all DDT audits in the same Run for the same page into one
companion request.

---

## What data to collect and how it maps to the unified model

| Panel | `Metric` records (long-term) | `Report.data` (pruned after 90 days) |
|-------|------------------------------|--------------------------------------------|
| SQL (`ddt-sql`) | `sql-query-count`, `sql-total-time-ms`, `sql-duplicate-count`, `sql-slowest-ms` | `queries: [{sql, time_ms, traceback}]` |
| Cache (`ddt-cache`) | `cache-calls`, `cache-hits`, `cache-misses`, `cache-total-time-ms` | `calls: [{command, key, time_ms}]` |

Additional panels that could be added later:

| Panel | `Metric` records | `Report.data` |
|-------|-----------------|--------------|
| Templates (`ddt-templates`) | `template-count` | `[{name, render_time_ms}]` |
| Signals (`ddt-signals`) | `signal-count` | `[{signal, receiver}]` |
| Request (`ddt-request`) | — | `{method, path, GET, POST, session_keys}` |
| Profiling (`ddt-profiling`) | — | `{top_functions}` |

**SQL panel is the primary value.** Query counts are environment-independent: the same
code paths execute regardless of where the app runs. Regressions show up locally.

**Two-tier storage rationale**: `Metric` records are the durable analytical signal.
`Report.data` contains SQL text, stack traces, and request parameters that may be
sensitive; these are pruned separately on a shorter schedule.

---

## Cadence and selectivity

A DDT Job selects `ddt-sql` and `ddt-cache` in its `audits` M2M and sets a crontab
and URL list. Since there is no per-panel boolean on the Job, dropping a panel means
removing the corresponding `Audit` from `Job.audits`.

Typical configuration:

```
# Monthly Lighthouse run
Job: site=mysite, audits=[lighthouse], schedule="0 0 1 * *"

# Hourly page-weight run
Job: site=mysite, audits=[page-weight], schedule="0 * * * *"

# Weekday DDT collection (local environment, explicit URL list)
Job: site=mysite-local, audits=[ddt-sql, ddt-cache],
     urls="https://localhost:8000/\nhttps://localhost:8000/about/",
     schedule="0 9 * * 1-5",
     config={"cricket_secret": "..."}
```

Using a separate `Site` record (e.g. `mysite-local` with `environment="local"`) makes
provenance unambiguous. Agents filter by site slug or environment.

---

## Local → shared server workflow

A developer running cricket locally collects DDT data. Only environment-independent
data is worth pushing to a shared server. Scalar metrics in `Metric` records are
portable; `Report.data` raw detail is not pushed.

See Stage 3 in `docs/development-plan.md` for the push API design.

---

## Implementation plan

### Phase 1: `Job.config` field

Add `config = JSONField(null=True, blank=True)` to `audits.Job`. Register it in the
admin. Write a migration.

### Phase 2: DDT audit registration

Data migration to create `Audit` records for `ddt-sql` and `ddt-cache` with their
task paths. Create `Definition` records for all DDT metrics.

### Phase 3: DDT task and report processor

**`apps/audits/tasks.py`** — add or extend `audit_ddt_page(run_id, audit_slug, page_id)`:

```
1. Load Run, Audit (slug=audit_slug), Page.
2. Read Job.config.get("cricket_secret", "").
3. Check settings.DDT_COLLECTION_ENABLED — raise non-retrying exception if False.
4. Make HTTP request to target page — extract store_id from HTML.
5. Request companion endpoint: /__cricket__/toolbar/?store_id=<id>&panels=<panel>.
6. Create Report(run, audit, page, data=<panel JSON>).
7. Call report processor to extract Metric records.
8. Call run.task_complete().
```

**`apps/audits/reports/ddt.py`** — report processor:

```python
def process(report: Report):
    data = report.data
    audit_slug = report.audit.slug

    if audit_slug == "ddt-sql":
        sql = data.get("SQLPanel", {}).get("sql_queries", [])
        upsert_metric(report, "sql-query-count", len(sql))
        upsert_metric(report, "sql-total-time-ms",
                      sum(q.get("time_ms", 0) for q in sql))
        upsert_metric(report, "sql-duplicate-count",
                      sum(1 for q in sql if q.get("is_duplicate")))
        if sql:
            upsert_metric(report, "sql-slowest-ms",
                          max(q.get("time_ms", 0) for q in sql))

    elif audit_slug == "ddt-cache":
        cache = data.get("CachePanel", {})
        calls = cache.get("calls", [])
        hits  = sum(1 for c in calls if c.get("cache_info") == "Hit")
        upsert_metric(report, "cache-calls", len(calls))
        upsert_metric(report, "cache-hits", hits)
        upsert_metric(report, "cache-misses", len(calls) - hits)
```

**`apps/audits/management/commands/prune_old_ddt_reports.py`**:

Clears `Report.data` on DDT reports older than N days, preserving the Metric records.

```bash
python manage.py prune_old_ddt_reports --days 90 --dry-run
```

### Phase 4: Companion middleware package (`django-cricket`)

**Estimated effort: 1–2 days** (separate repository, published to PyPI)

Minimal package, < 150 lines total. See the "Confirmed approach" section above.

---

## Proposed file structure

```
apps/
  audits/
    reports/
      ddt.py                        # Report processor for ddt-* audits
    management/
      commands/
        prune_old_ddt_reports.py    # Prune Report.data older than N days
    migrations/
      0009_job_config.py            # Add Job.config JSONField
      0010_ddt_audits.py            # Audit + Definition records (data migration)

# Companion package — separate repository:
django_cricket/
  __init__.py
  apps.py
  middleware.py
  views.py
  urls.py
  serializers.py
```

---

## Data retention

| Data | Retention | Rationale |
|------|-----------|-----------|
| Metric records (query_count, etc.) | 1 year | Trend analysis |
| Report.data (SQL text, stack traces) | 90 days | Sensitive; pruned in-place |
| Report records | 1 year | Consistent with other audits |

---

## Security considerations

1. **Collection is development-only.** `DDT_COLLECTION_ENABLED` gates the task.
   In staging/production the task raises a non-retrying exception.

2. **Companion endpoint.** Protected by `INTERNAL_IPS` + shared secret in request
   header. Secret stored in `Job.config["cricket_secret"]` — different Jobs use
   different secrets, set in the admin.

3. **Raw detail access.** `GET /api/sites/{slug}/runs/{id}/reports/{id}/` requires
   a valid Bearer token and returns `Report.data`. The same endpoint serves all audit
   types; there is no special restriction for DDT reports. Operators may choose to
   restrict API key distribution accordingly.

4. **SQL scrubbing.** The companion serialiser should offer `CRICKET_SCRUB_SQL = True`
   to replace parameter values with `?`. Recommended for staging. Default off.

5. **Push authentication.** The push endpoint (Stage 3) requires an admin API key.
   The management command requires the key to be passed explicitly.

---

## Open questions

| Question | Options | Recommendation |
|---|---|---|
| Batch companion requests | One HTTP request per DDT audit per page, or batch all DDT panels in one request | Batch: detect sibling DDT audits in same Run, fetch all panels in one companion call |
| `ddt-templates`, `ddt-signals` panels | Add now or defer | Defer until SQL/cache are validated |
| `ddt-profiling` | Expensive; requires special handling | Defer indefinitely |
| `prune_old_ddt_reports` scope | Clear just DDT reports or all reports? | DDT only — other audits store smaller structured data, not sensitive raw text |
