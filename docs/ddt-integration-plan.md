# Django Debug Toolbar Integration Plan

## Overview

This document analyses whether collecting django-debug-toolbar (DDT) data fits within
cricket's architecture, and if so, how to implement it. It also captures two significant
architectural questions that the DDT work brings into focus: selective collection and
environment integrity.

**Short answer on fit**: Yes — DDT data slots in cleanly as a fourth parallel collector
alongside lighthouse, headers, and pageweight.

**Two architectural questions surfaced by this work** (new sections below):
- Selective collection: how to support different collectors running at different frequencies
- Environment integrity: how to keep data from different environments unambiguous when
  multiple cricket instances push to a shared server

---

## Architecture Fit Analysis

### How the existing pattern works

Each of the three current collectors follows an identical structure:

```
sites.Scan (parent)
  └── <app>.Run (status, page_count)
        └── <app>.PageData (page = FK(sites.Page), collected, data fields or JSONField)
```

Tasks use Celery chords: a group of per-page tasks → a completion aggregator. All three
dispatchers are called in parallel from `sites.tasks.take_site_scan()`.

### Where DDT fits

A `debugtoolbar` app would slot in as a fourth entry in this pattern:

- `debugtoolbar.Run` → FK to `sites.Scan`
- `debugtoolbar.PageData` → FK to `sites.Page`, stores panel data
- `debugtoolbar.tasks.take_toolbar_scan` dispatched from `take_site_scan`
- An API router at `/api/sites/{slug}/scans/{id}/toolbar/`

No existing pattern needs to change. The only modification is adding one `.delay()` call
in `sites/tasks.py`.

### Key difference from the other collectors

The other collectors are black-box: they work against any HTTP server. DDT integration is
**cooperative** — the target application must be a Django app with DDT installed and
accessible. This means:

1. DDT collection is **opt-in**, enabled per-site.
2. Collection **only runs in development** (enforced at the settings level — cricket already
   gates `debug_toolbar` behind `DJANGO_ENV == "development" and DEBUG`).
3. The target app must expose panel data via the companion middleware package (see Phase 2).

### The local-collect → shared-serve workflow

The described workflow introduces a concept not yet in cricket: pushing data from one
cricket instance to another. The current architecture is pull-only. A sync mechanism
is needed:

- Local cricket: collects DDT data (and other metrics) from the local Django app.
- Remote/shared cricket: does not collect DDT data; only stores and serves it.
- A push command or API endpoint moves data from local to remote.

The data integrity implications of this are addressed in the **Environment Integrity**
section below.

---

## Technical Challenge: Extracting DDT Panel Data

Django Debug Toolbar stores panel data in Django's cache using a `store_id` generated per
request. The store_id is embedded in the response HTML (as `data-store-id` on the toolbar
container element) and/or in the `djdt` cookie.

### Alternative considered: cookie + `render_panel` endpoint

An earlier approach was to extract the `store_id` from the response and use DDT's
existing `/__debug__/render_panel/?store_id=<id>&panel_id=<id>` endpoint — the same AJAX
calls the browser makes when opening the toolbar sidebar. This requires no changes to the
target app.

**Why it was not chosen:**

- `render_panel` returns HTML formatted for display, not structured JSON. Extracting data
  requires parsing HTML, with a different parser needed per panel type.
- DDT **truncates** panel output for display performance (e.g. capping the visible query
  list). `panel.get_stats()` server-side returns the full dataset; the rendered HTML does
  not.
- Panel HTML layouts change between DDT versions. A minor DDT update silently breaks
  cricket's parsers.
- For trend analysis (the primary use case), reliable complete numbers matter. HTML
  parsing introduces fragility that is hard to test and diagnose.

The cookie/render_panel approach is practical for one-off browser automation or for
extracting a single badge-level metric (e.g. the query count shown in the toolbar badge).
It could serve as a zero-setup prototype to validate that the data is useful before
investing in the companion package. It is not a sound foundation for automated long-term
collection.

### Confirmed approach: thin companion middleware (`django-cricket`)

A minimal standalone Django package is installed in the target application.

**Package structure:**
```
django_cricket/
  __init__.py
  apps.py          # AppConfig: name="django_cricket"
  middleware.py    # Captures store_id after DDT processes request
  views.py         # JSON endpoint: GET /__cricket__/toolbar/?store_id=<id>
  urls.py          # urlpatterns for the endpoint
  serializers.py   # Converts DDT panel.get_stats() → clean JSON dict per panel
```

**The endpoint** (`/__cricket__/toolbar/`):

1. Receives `?store_id=<id>` from cricket's collector task.
2. Looks up the DDT store: `cache.get(f"djdt:{store_id}")`.
3. Calls `panel.get_stats()` on each enabled panel in the stored toolbar.
4. Returns a JSON response mapping panel names to their structured stats.

**Authentication**: Protected by shared secret + `INTERNAL_IPS` (the same mechanism DDT
uses for its own endpoints). The secret is stored in cricket's `Site.extra_config` JSONField
(already used for Lighthouse CLI flag overrides) — no new configuration model needed.

**Target app setup** (two lines):
```python
# settings.py (development only)
INSTALLED_APPS += ["django_cricket"]
CRICKET_SECRET = env.str("CRICKET_SECRET", default="")

# urls.py
urlpatterns += [path("__cricket__/", include("django_cricket.urls"))]
```

Cricket's collector task sends the shared secret in a request header when fetching
panel data. The package is published to PyPI; installation is `pip install django-cricket`.

---

## What Data to Collect

All DDT panels are collected. The scope can be narrowed per-site via a `panels` list in
`Site.extra_config` (defaulting to all panels). This mirrors how Lighthouse categories
can already be scoped via `extra_config`.

| Panel | Key scalar metrics stored | Raw data (JSONField, pruned separately) |
|-------|---------------------------|-----------------------------------------|
| SQL | query_count, total_time_ms, duplicate_count, slowest_query_ms | queries: [{sql, time_ms, traceback}] |
| Cache | total_calls, hits, misses, total_time_ms | calls: [{command, key, time_ms}] |
| Templates | template_count | templates: [{name, render_time_ms}] |
| Signals | signal_count | signals: [{signal, receiver}] |
| Request | — | request_data: {method, path, GET, POST, session_keys} |
| Profiling | — | profile: {top_functions} — off by default, expensive |

**Rationale for two tiers**: The scalar summary metrics (query_count, etc.) are the durable
analytical signal — the trend over time as features are added. The raw JSONFields contain
SQL text, stack traces, and request parameters that may include sensitive data; these are
pruned on a shorter schedule (see Retention below).

**SQL panel is the primary value**. The number of queries is largely
environment-independent: the same code paths execute regardless of where the app runs,
making query counts a reliable signal of regressions even when collected locally.

---

## Selective Collection Architecture

### The problem this work exposes

Currently every `sites.Scan` triggers all three collectors. The DDT integration
introduces a case where different metrics have naturally different collection frequencies:

- **Page load timing** (pageweight): hourly, to increase sample sizes and detect regressions quickly.
- **Lighthouse audits**: monthly or weekly — expensive, slow, and stable enough not to need
  hourly measurement.
- **DDT data**: on-demand or daily — tied to development work, not continuous monitoring.

### Two models compared

#### Model A: Multiple Site objects (current approach extended)

Each Site object has a specific set of enabled collectors and its own crontab. A site
wanting monthly Lighthouse + hourly pageweight would be two Site objects:

```
mysite-perf        crontab: "0 * * * *"   collectors: pageweight only
mysite-lighthouse  crontab: "0 0 1 * *"   collectors: lighthouse only
```

**Advantages**: Simple — the existing model changes minimally. Each site's page set can
differ (hourly monitoring on just 10 key pages, full audit on all 500).

**Disadvantages**: Duplicates URL/sitemap configuration when the page set is the same.
The API returns two separate sites; cross-collector comparison requires knowing to join
on URL rather than on scan.

#### Model B: One Site with per-collector schedules

One Site object but each collector has its own crontab and independently creates child
scans that are not necessarily grouped under a single parent scan.

**Advantages**: Clean data model when the page set is shared. One site in the API, but
multiple independent scan series (one for lighthouse, one for pageweight, one for DDT).

**Disadvantages**: Significant change to the current architecture. The `sites.Scan`
parent-as-coordinator model would need rethinking. The scan grouping currently provides
the "point in time" view; per-collector independence removes that.

### Decision

**Use Model A (multiple Site objects) for now.** It is consistent with the current
architecture and the tradeoffs are manageable.

The key enabler for Model A to work well is making per-collector opt-in per-site
explicit and clear in the admin and API. The following per-site flags (stored in a
`collectors` JSONField or as explicit BooleanFields on `Site`) control what runs:

```python
# sites.Site additions
enable_lighthouse = BooleanField(default=True)
enable_headers = BooleanField(default=True)
enable_pageweight = BooleanField(default=True)
enable_toolbar = BooleanField(default=False)  # DDT — local only
```

`take_site_scan` checks each flag before dispatching. This is a small change and
also makes the existing three collectors explicitly opt-out rather than always-on, which
improves clarity.

### Future path to Model B

If Model B becomes desirable, the key change is replacing the single `sites.Scan`
parent coordinator with per-collector scan series that each have their own `Site`
association and schedule. The parent scan would become optional metadata ("these
child scans were triggered together") rather than a required coordinator. This is
a larger refactor worth a separate design document.

---

## Environment Integrity

### The problem

The local-collect → shared-serve workflow creates a data integrity risk: a shared cricket
server could accumulate scans that contain data from different environments within
what appears to be a single site.

**Concrete scenario**: a team has `mysite` on both a local cricket instance and a staging
cricket instance, both pushing to a shared server. The shared server receives:

- Scan A from local: DDT query counts (useful, environment-independent) + pageweight
  (measured on a developer laptop — not representative of production)
- Scan B from staging: Lighthouse scores + headers + pageweight (measured on a
  realistic staging server)

If an agent or developer queries `GET /api/sites/mysite/scans/` they see both scans
with no indication that pageweight numbers from scan A are incomparable with scan B.
Trend analysis across these scans would be misleading.

### Solution: environment tagging on `sites.Scan`

Add an `environment` field to `sites.Scan`:

```python
class Run(TimeStampedModel, models.Model):
    # existing fields ...
    environment = CharField(
        max_length=50,
        default="",
        blank=True,
        help_text="Origin environment: local, staging, production, or blank for untagged"
    )
```

This is set when a scan is created (from `Site.extra_config["environment"]` or from
a push command argument) and is immutable after creation.

**API changes**:
- `ScanOut` includes `environment` field.
- `GET /api/sites/{slug}/scans/` supports `?environment=local` filter.
- `agent-context` endpoint documents the environment field and recommends filtering by it.

**Push command behaviour**: the push command requires `--environment` to be specified
(or reads it from the source scan). It never silently loses provenance.

### What is and is not environment-independent

This distinction matters for what should be pushed vs. collected natively:

| Metric | Environment-independent? | Recommendation |
|--------|--------------------------|----------------|
| SQL query count | Yes — same code paths execute | Collect locally, push |
| SQL query time | Partially — index performance varies | Push with caveat; tag as local |
| Cache hit/miss count | Yes — same logic executes | Collect locally, push |
| Page weight / request count | No — CDN, server, network differ | Collect on each target env |
| Lighthouse scores | No — latency, server speed matter | Collect on each target env |
| HTTP headers | Partially — some headers are env-specific | Collect on each target env |
| Template render count | Yes | Collect locally, push |
| Signal count | Yes | Collect locally, push |

The practical implication: when pushing a local scan to the shared server, include
only the DDT toolbar scan, not pageweight or lighthouse data from local. The push
command should support `--collectors toolbar` to push selected child scans only.

### Partial push (selective collector sync)

The push mechanism needs to support pushing only specific child scans from a parent.
Two ways to structure this on the remote:

**Option 1: Create a new remote scan tagged as local, with only toolbar data**

The remote server has two scan series for the site: one from staging (lighthouse +
headers + pageweight) and one from local (toolbar only). Each is unambiguous. An agent
querying both needs to join on scan time and URL to see the full picture.

**Option 2: Attach toolbar data to an existing remote scan**

The remote staging scan gets toolbar child scans attached from the local push.
This creates a single "complete" scan but with mixed provenance. Requires
per-child-scan environment tagging rather than just parent-level tagging.

**Recommendation: Option 1** for now. It is unambiguous and requires less model change.
The API already supports listing multiple scans for a site; an agent can query
`?environment=staging` and `?environment=local` separately. Option 2 can be reconsidered
if agents consistently struggle with joining across two scan series.

---

## Implementation Plan

### Phase 1: Per-collector opt-in on `Site` + new `debugtoolbar` app

**Estimated effort: 2–3 days**

#### 1a. Per-collector flags on `sites.Site`

Add four BooleanFields to `sites.Site`:

```python
enable_lighthouse = BooleanField(default=True)
enable_headers = BooleanField(default=True)
enable_pageweight = BooleanField(default=True)
enable_toolbar = BooleanField(default=False)
```

Update `take_site_scan` to check each flag. Update `SiteAdmin` to expose these fields.
This is a prerequisite for DDT and also cleans up the existing "always fire all collectors"
assumption.

#### 1b. Environment field on `sites.Scan`

Add `environment = CharField(max_length=50, default="", blank=True)` to `sites.Scan`.

Add `environment` to `Site.extra_config` schema documentation so operators know how to
set it (e.g. `{"environment": "local"}`). `create_scan()` reads this and stamps it
on the new Scan.

#### 1c. New `debugtoolbar` app

Create `apps/debugtoolbar/` following the identical pattern of `apps/headers/`.

**`apps/debugtoolbar/models/run.py`**
```python
class Run(TimeStampedModel, models.Model):
    scan = ForeignKey("sites.Scan", CASCADE, related_name="toolbar_run")
    status = CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    page_count = IntegerField(null=True, blank=True)
```

**`apps/debugtoolbar/models/page.py`**
```python
class Page(TimeStampedModel, models.Model):
    page = ForeignKey("sites.Page", CASCADE, related_name="toolbar_data")
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

    # Template panel
    template_count = IntegerField(null=True, blank=True)

    # Signal panel
    signal_count = IntegerField(null=True, blank=True)

    # Raw detail — pruned after 90 days (sensitive, large)
    sql_queries = JSONField(default=list)       # [{sql, time_ms, traceback}]
    cache_calls_detail = JSONField(default=list)  # [{command, key, time_ms}]
    templates = JSONField(default=list)         # [{name, render_time_ms}]
    signals = JSONField(default=list)           # [{signal, receiver}]
    request_data = JSONField(default=dict)      # {method, path, GET, POST, session_keys}

    class Meta:
        
```

**`apps/debugtoolbar/tasks.py`** — identical structure to `headers/tasks.py`:
```
take_toolbar_scan(scan_pk)
collect_page_panels(page_pk)
complete_toolbar_run(run_pk)
```

`collect_page_panels` makes two HTTP requests:
1. The page itself (triggers DDT data collection, returns `store_id` in HTML/cookie).
2. `/__cricket__/toolbar/?store_id=<id>` on the companion endpoint (returns panel JSON).

It reads `CRICKET_SECRET` from `Site.extra_config` for the second request's auth header.
Checks `settings.DDT_COLLECTION_ENABLED` at the top of the task; raises a non-retrying
exception if False (so the scan transitions to `failed` with a clear message).

**Settings addition:**
```python
DDT_COLLECTION_ENABLED = DJANGO_ENV == "development" and DEBUG
```

**`apps/debugtoolbar/management/commands/prune_old_toolbar_data.py`**

Analogous to `lighthouse`'s `prune_old_reports`. Nullifies the five raw JSONFields on
`Page` records older than N days (default 90), while preserving all scalar fields. The
`--dry-run` flag is required.

```bash
python manage.py prune_old_toolbar_data --days 90 --dry-run
```

---

### Phase 2: Companion middleware package (`django-cricket`)

**Estimated effort: 1–2 days** (separate repository)

Minimal package, < 150 lines total.

**`serializers.py`** — the core of the package. Knows how to extract stats from each
DDT panel type and return a plain dict. Panel keys follow DDT's own naming
(`SQLPanel`, `CachePanel`, etc.) to make the mapping obvious.

**`views.py`** — the single endpoint:

```python
@require_GET
def toolbar_data(request):
    if not authenticate(request):  # checks CRICKET_SECRET + INTERNAL_IPS
        return JsonResponse({"error": "Forbidden"}, status=403)
    store_id = request.GET.get("store_id")
    if not store_id:
        return JsonResponse({"error": "store_id required"}, status=400)
    toolbar = cache.get(f"djdt:{store_id}")
    if toolbar is None:
        return JsonResponse({"error": "store not found"}, status=404)
    data = {panel_id: serialize_panel(panel) for panel_id, panel in toolbar.panels.items()}
    return JsonResponse(data)
```

**Panel selection**: the endpoint accepts an optional `?panels=SQLPanel,CachePanel`
parameter so cricket can request only the panels it needs. This avoids transferring
profiling data unless explicitly requested.

---

### Phase 3: API exposure

**Estimated effort: 1 day**

Add `apps/api/routers/toolbar.py`.

```
GET /api/sites/{slug}/scans/{scan_id}/toolbar/
    → ToolbarRunOut: status, page_count, sql_avg_queries, sql_max_queries,
                          sql_avg_time_ms, cache_hit_rate_avg

GET /api/sites/{slug}/scans/{scan_id}/toolbar/pages/
    → paginated ToolbarPageListOut: url, sql_query_count, sql_total_time_ms,
                                    sql_duplicate_count, cache_hits, cache_misses,
                                    template_count, signal_count

GET /api/sites/{slug}/scans/{scan_id}/toolbar/pages/{page_id}/
    → ToolbarPageDetailOut: all scalar fields + raw JSONFields
                            (raw fields null if pruned)
```

Update `ScanOut` to include:
- `environment: str` — the origin environment tag
- `toolbar_url: str | None` — null unless site has `enable_toolbar=True`

Update `GET /api/sites/{slug}/scans/` to support `?environment=<tag>` filter.

Update `agent-context` to document the environment field, the toolbar endpoints, and
the guidance that pageweight/lighthouse from different environments should not be
compared directly.

---

### Phase 4: Data sync (local → shared server)

**Estimated effort: 2–3 days**

#### Push API endpoint (preferred — agent-operable)

Add an admin-authenticated API endpoint:

```
POST /api/sites/{slug}/scans/push/
Authorization: Bearer <admin-api-key>
Content-Type: application/json

{
  "environment": "local",
  "collectors": ["toolbar"],   # optional — defaults to all present collectors
  "scans": { ...serialised child scans... }
}
```

The request body is generated by a management command on the source cricket instance:

```bash
python manage.py push_scan <scan_id> \
    --remote https://cricket.example.com \
    --key <admin-token> \
    --collectors toolbar \
    --environment local
```

Key behaviours of the push:
- `--collectors` limits which child scans are included. Default: all completed child
  scans. For DDT-only pushes from local, `--collectors toolbar` is used.
- `--environment` overrides the source scan's environment tag on the remote. If the
  source is already tagged correctly this is optional.
- The remote creates a new `sites.Scan` with `status=COMPLETE` and the specified
  environment tag. If the site slug doesn't exist on the remote, a stub is created.
- Files (lighthouse HTML reports) are not transferred. Remote records have null file fields.

#### Why the push is scoped to selected collectors

This directly addresses the mixed-environment data integrity concern. A developer running
locally pushes only toolbar data:

```bash
python manage.py push_scan 42 --collectors toolbar --environment local
```

The shared server receives a scan with only toolbar data, tagged as `local`. It does
not receive local pageweight or lighthouse data. An agent querying the shared server sees:

- `GET /api/sites/mysite/scans/?environment=staging` → lighthouse, headers, pageweight
- `GET /api/sites/mysite/scans/?environment=local` → toolbar only

The agent can join on time and URL, knowing which metrics are from which environment.
Each number is interpretable without ambiguity.

---

## Data Retention

| Data | Retention | Rationale |
|------|-----------|-----------|
| Scalar stats (query_count, etc.) | 1 year | Drift analysis over time as features are added |
| Raw JSONFields (sql_queries, etc.) | 90 days | Sensitive (SQL text, stack traces, request params) |
| Scan/Page records | 1 year | Consistent with other collectors |

The `prune_old_toolbar_data` command nullifies the five raw JSONFields in-place rather
than deleting the Page record. The scalar stats remain for trend analysis. This is
different from the lighthouse pruning which deletes the file-backed raw report but keeps
the derived metrics.

---

## Security Considerations

1. **Collection is development-only**: `DDT_COLLECTION_ENABLED` gates collection tasks.
   In production the task is a no-op. The companion endpoint is only reachable from
   `INTERNAL_IPS` and requires the shared secret.

2. **Companion endpoint**: Protected by `INTERNAL_IPS` + shared secret in header. The
   secret lives in `Site.extra_config`, not in cricket settings, so different sites can
   have different secrets (useful if multiple projects share one cricket instance).

3. **Shared server access to DDT data**: SQL text, stack traces, and request parameters
   may be sensitive. Admin key scoping (`APIKey.is_admin`) should be required for the
   raw detail endpoint (`/toolbar/pages/{id}/`). The list endpoint (scalar stats only)
   can be accessible to normal site-scoped keys.

4. **SQL scrubbing option**: The companion package serialiser should offer a
   `CRICKET_SCRUB_SQL = True` setting that replaces parameter values with `?` before
   returning them. Recommended for any staging use. Default off (local development data
   is typically not sensitive).

5. **Push authentication**: The push endpoint requires `APIKey.is_admin = True`. The
   management command requires the admin key to be passed explicitly — it cannot read
   it from environment config automatically, to prevent accidental pushes.

6. **Environment tag immutability**: Once set on a Scan, the environment tag cannot
   be changed via the API. Only the push command (admin key required) sets it at
   creation time.

---

## Proposed File Structure

```
apps/
  debugtoolbar/
    __init__.py
    apps.py
    admin/
      __init__.py
      scan.py
      page.py
    management/
      commands/
        prune_old_toolbar_data.py
    migrations/
    models/
      __init__.py
      scan.py
      page.py
    tasks.py
  api/
    routers/
      toolbar.py              (new)
  sites/
    models/
      site.py                 (add enable_* flags, environment in extra_config docs)
      scan.py             (add environment field)
    tasks.py                  (check enable_* flags before dispatching)

# Companion package — separate repository:
django_cricket/
  __init__.py
  apps.py
  middleware.py
  views.py
  urls.py
  serializers.py

# Sync management commands:
apps/sites/management/commands/
  push_scan.py            (Phase 4)
```

---

## Summary of Changes

| Component | Change | Phase |
|-----------|--------|-------|
| `sites.Site` | Add `enable_lighthouse/headers/pageweight/toolbar` flags | 1a |
| `sites.Scan` | Add `environment` field | 1b |
| `sites/tasks.py` | Check enable flags before dispatching | 1a |
| `sites/models/site.py` | `create_scan()` reads environment from `extra_config` | 1b |
| `apps/debugtoolbar/` | New app — models, tasks, admin, prune command | 1c |
| `config/settings.py` | Add `DDT_COLLECTION_ENABLED` | 1c |
| `django-cricket` package | Companion middleware for target app (separate repo) | 2 |
| `api/routers/toolbar.py` | New router, 3 endpoints | 3 |
| `api/routers/scans.py` | Add `environment` field, `?environment` filter | 3 |
| `api/routers/introspection.py` | Document environment and toolbar in agent-context | 3 |
| `push_scan` command | Push selected collectors to remote cricket | 4 |
| Remote push API endpoint | Accept incoming scan data (admin key required) | 4 |

**Effort estimate**: ~10–12 days total. Phase 1 is the foundation (3 days). Phase 2 is
independent and can be done in parallel (2 days). Phase 3 follows Phase 1 (1 day).
Phase 4 is standalone after Phase 1 and 3 are complete (3 days).

---

## Decisions Made

| Question | Decision |
|----------|----------|
| Companion package vs. shared Redis | Companion package (`django-cricket`) |
| Which panels to collect | All panels; selective via `Site.extra_config["panels"]` |
| Staging support | Not planned — local is the primary and simplest case |
| Sync mechanism | Push API endpoint (agent-operable); management command generates payload |
| Data retention for DDT | Scalar stats: 1 year; raw JSONFields: 90 days (pruned in-place) |
| Selective collection model | Multiple Site objects (Model A); per-collector enable flags on Site |
| Environment integrity | `environment` field on Scan; push scoped to selected collectors |
