# Cricket — Development Plan

This document captures all planned refinements, features, and future ideas in one place.
Its purpose is to prevent good ideas from being lost while keeping day-to-day work
focused. Nothing here is committed to or scheduled; it is a reference for prioritisation
discussions.

---

## Architectural decisions

The reasoning behind architectural choices is in `docs/decisions.md`.
Read that before proposing structural changes.

---

## Target model structure

Cricket is a collection of independent collector tools deployed together and sharing a
common framework. Tools are not coupled — each runs against its own URL list on its own
schedule. A `Job` is the unit of configuration: one collector, one URL source, one
schedule. A `Run` is one execution of a Job.

```
sites.Site    (stable identity — what agents and humans refer to)
  └── <collector>.Job  (per-tool configuration · URL source · schedule)
        └── <collector>.Run   (one execution of a Job)
              └── <collector>.Page  (one URL · collector-specific results)
```

**`sites.Site`** — identity only. No URL source, no schedule, no tool flags.

```
name, slug, primary_url, description
```

**Job models** — each tool owns its Job model with typed, tool-specific fields.
Common fields live in a shared abstract base; tool-specific configuration is explicit
rather than stored in a JSON blob.

```python
# Abstract base — fields shared by every Job model
class BaseJob(TimeStampedModel):
    site        = FK(Site)
    url_source  = CharField  [sitemap_url | sitemap_file | url_list]
    url_value   = TextField  (sitemap URL, file path, or newline-separated URL list)
    environment = CharField  [local | staging | production | '']
    crontab     = CharField
    enabled     = BooleanField

# Per-tool Job models with typed configuration fields
class lighthouse.Job(BaseJob):
    platform    = CharField  [mobile | desktop]
    categories  = MultiSelectField  [performance | accessibility | best-practices | seo]

class headers.Job(BaseJob):
    pass  # no tool-specific configuration

class pageweight.Job(BaseJob):
    device      = CharField  [mobile | desktop]

class debugtoolbar.Job(BaseJob):
    panels      = MultiSelectField  [sql | cache | templates | signals | request | profiling]
                  # profiling excluded from default — expensive and off by default in DDT
```

Tool-specific config (Lighthouse CLI flags, DDT panel query params) is derived from
these fields at dispatch time — not stored as a blob. Different cadences or different
scopes for the same site → separate Jobs.

**Per-collector models** — each collector owns its page list. No shared URL model.

```
lighthouse.Run    → FK(lighthouse.Job)
lighthouse.Page   → FK(lighthouse.Run)  [url · report files · audited flag]
  └── lighthouse.PageCategory  → FK(lighthouse.Page)
  └── lighthouse.PageAudit     → FK(lighthouse.Page)
  └── lighthouse.AuditDefinition  (stable slugs — see audit_ids.py)

headers.Run   → FK(headers.Job)
headers.Page  → FK(headers.Run)   [url · headers · status_code · redirect_count]

pageweight.Run  → FK(pageweight.Job)
pageweight.Page → FK(pageweight.Run)  [url · transfer sizes by type]
  └── pageweight.Resource  → FK(pageweight.Page)

debugtoolbar.Run  → FK(debugtoolbar.Job)
debugtoolbar.Page → FK(debugtoolbar.Run)  [url · scalar panel metrics · raw JSONFields]
```

---

## API structure

Tool-first URL layout. Each tool contributes its own router independently; the `api`
app assembles them. An agent working with one tool never has to know about others.
The URL string is the join key across tools and across time.

```
GET  /api/sites/
GET  /api/sites/{slug}/

# Per-tool job configuration (typed fields — no JSON blob)
GET  /api/sites/{slug}/lighthouse/jobs/
POST /api/sites/{slug}/lighthouse/jobs/
GET  /api/sites/{slug}/lighthouse/jobs/{id}/

GET  /api/sites/{slug}/headers/jobs/
GET  /api/sites/{slug}/pageweight/jobs/
GET  /api/sites/{slug}/toolbar/jobs/

# Per-tool run history and results
GET  /api/sites/{slug}/lighthouse/runs/
GET  /api/sites/{slug}/lighthouse/runs/latest/
POST /api/sites/{slug}/lighthouse/runs/
GET  /api/sites/{slug}/lighthouse/runs/{id}/
GET  /api/sites/{slug}/lighthouse/runs/{id}/pages/
GET  /api/sites/{slug}/lighthouse/runs/{id}/pages/{page_id}/

GET  /api/sites/{slug}/headers/runs/
GET  /api/sites/{slug}/headers/runs/latest/
POST /api/sites/{slug}/headers/runs/
GET  /api/sites/{slug}/headers/runs/{id}/pages/

GET  /api/sites/{slug}/pageweight/runs/
GET  /api/sites/{slug}/pageweight/runs/latest/
POST /api/sites/{slug}/pageweight/runs/
GET  /api/sites/{slug}/pageweight/runs/{id}/pages/

GET  /api/sites/{slug}/toolbar/runs/
GET  /api/sites/{slug}/toolbar/runs/latest/
GET  /api/sites/{slug}/toolbar/runs/{id}/pages/
GET  /api/sites/{slug}/toolbar/runs/{id}/pages/{page_id}/
```

Filter parameters on run list endpoints: `?environment=`, `?status=`, date range.
Filter on job list endpoints: `?categories=performance` (lighthouse),
`?panels=sql,cache` (toolbar). Results for a given URL across time: filter by URL
on the pages endpoint.

Each tool's router is self-contained in its own app (`lighthouse/api.py`,
`headers/api.py`, etc.) and registered in `api/api.py` with a single line per tool.
Adding a new collector adds one registration; nothing else changes.

---

## Stage 0 — Foundation refinements ✓

All items complete. Implementation will be superseded by the Stage A refactoring
below, but the decisions and learnings remain valid.

- ~~SQLite chosen over PostgreSQL~~
- ~~Snapshot → Scan rename~~
- ~~Shared `sites.Page` introduced~~ *(to be removed in Stage A)*
- ~~Pre-aggregation removed~~
- ~~Lighthouse audit IDs stabilised (`audit_ids.py`)~~
- ~~Collector completion signalling fixed~~
- ~~API test coverage improved~~
- ~~Deployment story confirmed~~
- ~~`AGENTS.md` and `agent-context` reviewed~~

---

## Stage 1 — Per-tool enable flags and environment tagging ✓

Implemented as designed. The `enable_*` flags on `Site` and the `environment` field on
`Scan` will be superseded by Stage A: enable/disable becomes Job existence, and
`environment` moves to `Job`. The concepts are correct; only the model location changes.

---

## Stage A — Architectural refactoring (current priority)

*Supersedes the Scan/shared-Page structure from Stages 0–1.*

The reasoning is in `docs/decisions.md`. Summary: tools are independent (toolbox, not
swiss army knife), per-tool `Job` models replace the role `Site` was playing as
configuration, each tool owns its own page list, and the URL string is the join key
across tools.

- **Introduce per-tool Job models** with an abstract `BaseJob` for shared fields.
  Each tool's `Job` has typed, tool-specific fields: `lighthouse.Job` has `platform`
  and `categories`; `pageweight.Job` has `device`; `headers.Job` has no tool-specific
  fields. Tool-specific config is derived from these fields at dispatch time.
- **Simplify `sites.Site`**: name, slug, primary_url, description only.
- **Remove `sites.Scan` and `sites.Page`**: coordination overhead that couples tools.
- **Restore per-tool Page models**: each collector's `Run` owns its URL list. Each
  `Page` belongs to a `Run`, not to a shared parent.
- **Restructure each collector's `Run`**: `FK(<tool>.Job)` instead of `FK(sites.Scan)`.
- **Restructure tasks**: each tool's task is triggered independently; `signal_scan_complete`
  goes away (each Run completes on its own).
- **Make each tool app self-contained**: its own Job model, Run model, Page model,
  tasks, admin, and API router. The `api` app assembles routers with one line per tool.
- **Restructure the API**: tool-first URL layout as above. Remove `/scans/` endpoints.
  Add per-tool `/jobs/` endpoints exposing typed configuration fields.
- **Update `AGENTS.md`** and `agent-context` to reflect the new structure.
- **Single focused commit** — this touches every app and every test.

---

## Stage 2 — Django Debug Toolbar integration

*Depends on Stage A.*

Detailed design in `docs/ddt-integration-plan.md`. DDT slots in as a fourth independent
collector following the same Job/Run/Page pattern as the others.

- New `apps/debugtoolbar/` app, fully self-contained.
- `debugtoolbar.Job(BaseJob)` adds `panels` MultiSelectField — which DDT panels to
  collect. Profiling excluded from default (expensive, off by default in DDT itself).
  Selected panels are translated to the companion endpoint's `?panels=` query parameter
  at dispatch time.
- `debugtoolbar.Run` → FK(debugtoolbar.Job). `debugtoolbar.Page` → FK(Run).
- Requires companion package `django-cricket` installed in the target app.
- Development/local environment only (`Job.environment = "local"`).
- Primary metric: SQL query count per page.
- `agent-context` must document all JSONField structures.

---

## Stage 3 — Multi-instance sync (local → shared server)

*Depends on Stage A and Stage 2.*

A local cricket instance collects DDT data and pushes it to a shared team server.
Only environment-independent data is pushed (SQL query counts, cache stats). Pageweight
and Lighthouse scores are not pushed — they must be collected on the target environment.

- **Push API endpoint**: `POST /api/sites/{slug}/toolbar/runs/push/` (admin key required).
  Accepts a serialised Run including its Pages.
- **`push_run` management command**: `--job <id>` selects which Job's latest Run to push.
- Environment provenance: the `Job.environment` field on the source run is preserved on
  the remote. Agents filter by `?environment=local` to see pushed DDT data.

---

## Stage 4 — JS and CSS coverage

*Depends on Stage A. Extends the pageweight collector.*

Chrome DevTools Protocol Coverage API, same Puppeteer session as pageweight.
`pageweight.PageCoverage` → FK(pageweight.Page).

- Per-script/stylesheet: used bytes, unused bytes, coverage percentage.
- Per-function detail for non-minified builds; per-CSS-rule detail.
- Raw detail pruned on same schedule as DDT raw data.
- Key limitation: interaction-triggered code appears unused. Frame as "not executed
  during page load."

---

## Stage 5 — Cold/warm cache comparison

*Depends on Stage A. Extends the pageweight collector.*

Second Puppeteer pass in the same collection task. Results as additional fields on
`pageweight.Page` (warm_transfer_size, cache_saving_bytes, cache_saving_pct).

---

## Stage 6 — HTML validation

*Depends on Stage A. New collector following the headers pattern.*

W3C Nu Html Checker JSON API, one POST per page.
`htmlvalidation.Run` + `htmlvalidation.Page` following the standard collector pattern.

- `error_count`, `warning_count` as scalar fields.
- Full message list in JSONField: `[{message, type, line, column}]`.

---

## Stage 7 — Broken link detection

*Depends on Stage A. New collector following the headers pattern.*

Per-page link extraction and HEAD request checking.
`linkcheck.Run` + `linkcheck.Page` following the standard collector pattern.

- `broken_count`, `redirect_count` as scalar fields.
- Full link list in JSONField: `[{url, status_code, source_url}]`.
- JS-injected links need the Puppeteer session; static HTML needs only `requests`.

---

## Future ideas (no stage assigned)

**Carbon footprint estimate**
Derived from pageweight transfer size via the Website Carbon API. A computed field
on `pageweight.Page`, no separate collection task needed.

**DNS and TLS analysis**
Per-domain rather than per-page. Overlaps with headers data. Revisit when security
auditing requirements are clearer.

**Rendered DOM capture**
Post-JS DOM capture for SSR/hydration mismatch detection. Niche; consider when there
is a specific need.

**First-party vs third-party resource breakdown**
Derivable from `pageweight.Resource` URL data at query time. Not a new collection task.

**Structured data validation**
Schema.org / Open Graph tag validation. Lighthouse covers some of this already.

**URL list as explicit input**
`Job.url_source = url_list` with a newline-separated list of URLs stored in
`Job.url_value`. Allows auditing an arbitrary set of URLs — including the home pages
of multiple different domains in a single Job — without a sitemap.
