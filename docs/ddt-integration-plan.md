# Django Debug Toolbar Integration Plan

## Overview

This document describes how to integrate Django Debug Toolbar (DDT) data collection
into cricket as a fourth independent collector. DDT differs from the other collectors
in two important ways: it requires a cooperative target application, and its most
valuable metrics (SQL query counts) are environment-independent, making local
collection meaningful on a shared server.

---

## Architecture fit

DDT slots into cricket as a standard collector — a `debugtoolbar` app following the
same Job/Run/Page pattern as `lighthouse`, `headers`, and `pageweight`.

```
sites.Job  (collector="toolbar", url_source=..., environment="local", crontab=...)
  └── debugtoolbar.Run   (status, page_count)
        └── debugtoolbar.Page  (url · scalar metrics · raw JSONFields)
```

A DDT Job is configured like any other Job: attached to a Site, with its own URL
source, schedule, and `environment` field. Setting `environment="local"` on the Job
makes it unambiguous that data came from a developer machine. Agents filter by
`?environment=local` on the toolbar runs endpoint to see only DDT data.

The distinction from other collectors:

| | Other collectors | DDT |
|---|---|---|
| Target | Any HTTP server | Django app with DDT installed |
| Environment | staging / production | local only |
| Value | Load time, headers, security | SQL query counts, cache behaviour |
| Env-independence | No — results differ by environment | Yes — same code paths execute locally |

---

## Technical challenge: extracting DDT panel data

Django Debug Toolbar stores panel data in Django's cache using a `store_id` generated
per request. The store_id is embedded in the response HTML (as `data-store-id` on the
toolbar container) and/or in the `djdt` cookie.

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
in the Job's `config` JSONField (`config["cricket_secret"]`) — no new configuration
model needed, and different Jobs can use different secrets.

**Target app setup:**
```python
# settings.py (development only)
INSTALLED_APPS += ["django_cricket"]
CRICKET_SECRET = env.str("CRICKET_SECRET", default="")

# urls.py
urlpatterns += [path("__cricket__/", include("django_cricket.urls"))]
```

Cricket sends the secret in a request header when fetching panel data. Installation:
`pip install django-cricket`.

**Panel selection**: the endpoint accepts `?panels=SQLPanel,CachePanel` so cricket
can request only the panels it needs. The Job's `config["panels"]` list controls
which panels to request (default: all).

---

## What data to collect

| Panel | Scalar metrics (kept 1 year) | Raw data (JSONField, pruned after 90 days) |
|-------|------------------------------|--------------------------------------------|
| SQL | query_count, total_time_ms, duplicate_count, slowest_query_ms | queries: [{sql, time_ms, traceback}] |
| Cache | total_calls, hits, misses, total_time_ms | calls: [{command, key, time_ms}] |
| Templates | template_count | templates: [{name, render_time_ms}] |
| Signals | signal_count | signals: [{signal, receiver}] |
| Request | — | request_data: {method, path, GET, POST, session_keys} |
| Profiling | — | profile: {top_functions} — off by default, expensive |

**SQL panel is the primary value.** Query counts are environment-independent: the same
code paths execute regardless of where the app runs. Regressions show up locally.

**Two-tier storage rationale**: scalar summary metrics are the durable analytical signal.
Raw JSONFields contain SQL text, stack traces, and request parameters that may be
sensitive; these are pruned separately on a shorter schedule.

---

## Cadence and selectivity

A DDT Job has its own crontab and URL source, independent of Lighthouse or pageweight
Jobs for the same site. Typical configuration:

```
Job A: site=mysite, collector=lighthouse,  crontab="0 0 1 * *"  (monthly)
Job B: site=mysite, collector=pageweight,  crontab="0 * * * *"   (hourly)
Job C: site=mysite, collector=toolbar,     crontab="0 9 * * 1-5" (weekday mornings)
         environment=local, url_source=url_list, url_value="https://localhost:8000/\n..."
```

Job C runs against localhost; the other Jobs run against staging or production. The
`environment` field on each Job makes provenance explicit. This replaces the
`enable_toolbar` flag approach that was considered earlier: a Job existing is the
enablement signal.

---

## Local → shared server workflow

A developer running cricket locally collects DDT data. Only environment-independent
data (SQL counts, cache stats) is worth pushing to a shared server. Pageweight and
Lighthouse must be measured on the target environment, not pushed from local.

**What is and is not environment-independent:**

| Metric | Env-independent? | Recommendation |
|--------|-----------------|----------------|
| SQL query count | Yes | Collect locally, push |
| SQL query time | Partially | Push with caveat; environment tag makes it clear |
| Cache hit/miss | Yes | Collect locally, push |
| Page weight | No | Collect on target env only |
| Lighthouse scores | No | Collect on target env only |
| HTTP headers | Partially | Collect on target env only |

**Push mechanism** (Stage 3 in `docs/development-plan.md`):

```bash
python manage.py push_run <run_id> \
    --remote https://cricket.example.com \
    --key <admin-token>
```

The command serialises the Run and its Pages and POSTs to the remote:

```
POST /api/sites/{slug}/toolbar/runs/push/
Authorization: Bearer <admin-api-key>
```

The remote creates a new `debugtoolbar.Run` and its pages, preserving the source
`Job.environment` tag. An agent querying the shared server sees:

- `GET /api/sites/mysite/lighthouse/runs/?environment=staging` → production-quality data
- `GET /api/sites/mysite/toolbar/runs/?environment=local` → DDT data from local

---

## Implementation plan

### Phase 1: `debugtoolbar` app

**Estimated effort: 2–3 days**

Create `apps/debugtoolbar/` following the `headers` app as the reference pattern.

**`apps/debugtoolbar/models/run.py`**
```python
class Run(TimeStampedModel, models.Model):
    job = ForeignKey("sites.Job", CASCADE, related_name="toolbar_runs")
    status = CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    page_count = IntegerField(null=True, blank=True)
```

**`apps/debugtoolbar/models/page.py`**
```python
class Page(TimeStampedModel, models.Model):
    run = ForeignKey(Run, CASCADE, related_name="pages")
    url = URLField(max_length=2000)
    collected = BooleanField(default=False)
    error = TextField(blank=True)

    # SQL panel — scalar stats kept long-term
    sql_query_count = IntegerField(null=True, blank=True)
    sql_total_time_ms = FloatField(null=True, blank=True)
    sql_duplicate_count = IntegerField(null=True, blank=True)
    sql_slowest_ms = FloatField(null=True, blank=True)

    # Cache panel — scalar stats kept long-term
    cache_calls = IntegerField(null=True, blank=True)
    cache_hits = IntegerField(null=True, blank=True)
    cache_misses = IntegerField(null=True, blank=True)
    cache_total_time_ms = FloatField(null=True, blank=True)

    # Template and signal panels
    template_count = IntegerField(null=True, blank=True)
    signal_count = IntegerField(null=True, blank=True)

    # Raw detail — pruned after 90 days
    sql_queries = JSONField(default=list)         # [{sql, time_ms, traceback}]
    cache_calls_detail = JSONField(default=list)  # [{command, key, time_ms}]
    templates = JSONField(default=list)           # [{name, render_time_ms}]
    signals = JSONField(default=list)             # [{signal, receiver}]
    request_data = JSONField(default=dict)        # {method, path, GET, POST, session_keys}
```

**`apps/debugtoolbar/tasks.py`** — same chord pattern as `headers/tasks.py`:
```
take_toolbar_scan(job_pk)   → creates Run, dispatches per-page tasks
collect_page_panels(page_pk) → makes two HTTP requests, populates Page
complete_toolbar_run(run_pk) → sets status=COMPLETE, page_count
```

`collect_page_panels` makes two HTTP requests:
1. The page itself — triggers DDT data collection, returns `store_id` in HTML.
2. `/__cricket__/toolbar/?store_id=<id>` — returns structured panel JSON.

The `CRICKET_SECRET` is read from `job.config["cricket_secret"]`.

Checks `settings.DDT_COLLECTION_ENABLED` at the top; raises a non-retrying exception
if False, so the Run transitions to `failed` with a clear message.

```python
# config/settings.py
DDT_COLLECTION_ENABLED = DJANGO_ENV == "development" and DEBUG
```

**`apps/debugtoolbar/management/commands/prune_old_toolbar_data.py`**

Nullifies the five raw JSONFields on Page records older than N days (default 90),
preserving all scalar fields. The `--dry-run` flag is required.

```bash
python manage.py prune_old_toolbar_data --days 90 --dry-run
```

---

### Phase 2: Companion middleware package (`django-cricket`)

**Estimated effort: 1–2 days** (separate repository, published to PyPI)

Minimal package, < 150 lines total. See the "Confirmed approach" section above for
the endpoint specification.

---

### Phase 3: API exposure

**Estimated effort: 1 day**

Add `apps/api/routers/toolbar.py`.

```
GET  /api/sites/{slug}/toolbar/runs/
GET  /api/sites/{slug}/toolbar/runs/latest/
GET  /api/sites/{slug}/toolbar/runs/{id}/
     → RunOut: status, page_count, sql_avg_queries, sql_max_queries, sql_avg_time_ms,
               cache_hit_rate_avg, environment, created

GET  /api/sites/{slug}/toolbar/runs/{id}/pages/
     → paginated PageListOut: url, sql_query_count, sql_total_time_ms,
                              sql_duplicate_count, cache_hits, cache_misses,
                              template_count, signal_count

GET  /api/sites/{slug}/toolbar/runs/{id}/pages/{page_id}/
     → PageDetailOut: all scalar fields + raw JSONFields (null if pruned)
```

Filter parameters: `?environment=`, `?status=`.

Update `agent-context` to document the toolbar endpoints, the environment field, and
the guidance that pageweight/Lighthouse from different environments should not be
compared directly.

---

### Phase 4: Push to shared server

**Estimated effort: 2–3 days**

See Stage 3 in `docs/development-plan.md`. Cricket-specific detail:

```
POST /api/sites/{slug}/toolbar/runs/push/
Authorization: Bearer <admin-api-key>
Content-Type: application/json

{
  "run": { ...serialised Run + Pages... }
}
```

The remote creates a new `debugtoolbar.Run` with `status=COMPLETE` and attaches the
Pages. Source `Job.environment` is preserved. HTML reports and file fields are not
transferred (null on the remote).

---

## Proposed file structure

```
apps/
  debugtoolbar/
    __init__.py
    apps.py
    admin/
      __init__.py
      run.py
      page.py
    management/
      commands/
        prune_old_toolbar_data.py
    migrations/
    models/
      __init__.py
      run.py
      page.py
    tasks.py
  api/
    routers/
      toolbar.py
  sites/
    management/
      commands/
        push_run.py          (Phase 4)

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
| Scalar stats (query_count, etc.) | 1 year | Trend analysis as features are added |
| Raw JSONFields (sql_queries, etc.) | 90 days | Sensitive — SQL text, stack traces, request params |
| Run / Page records | 1 year | Consistent with other collectors |

---

## Security considerations

1. **Collection is development-only.** `DDT_COLLECTION_ENABLED` gates collection tasks.
   In production the task is a no-op. The companion endpoint is only reachable from
   `INTERNAL_IPS` and requires the shared secret.

2. **Companion endpoint.** Protected by `INTERNAL_IPS` + shared secret in request header.
   Secret stored in `Job.config["cricket_secret"]` — different Jobs can use different
   secrets.

3. **Raw detail endpoint.** `GET /toolbar/runs/{id}/pages/{id}/` requires an admin API
   key. The list endpoint (scalar stats only) is accessible to site-scoped keys.

4. **SQL scrubbing.** The companion serialiser should offer `CRICKET_SCRUB_SQL = True`
   to replace parameter values with `?`. Recommended for staging. Default off.

5. **Push authentication.** The push endpoint requires `APIKey.is_admin = True`. The
   management command requires the key to be passed explicitly to prevent accidental pushes.

---

## Decisions

| Question | Decision |
|---|---|
| Companion package vs. shared Redis | Companion package (`django-cricket`) |
| Panels to collect | All panels; Job `config["panels"]` narrows selection |
| Cadence | Separate Job with its own crontab — not coupled to other collectors |
| Enable/disable | Job existence is the signal — no enable flag on Site |
| Environment provenance | `Job.environment` field; preserved on push |
| Selective push | Push one Run (toolbar only) — no concept of "partial scan" |
| Data retention | Scalar: 1 year; raw JSONFields: 90 days pruned in-place |
