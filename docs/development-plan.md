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

```
sites.Site
  └── sites.Scan          (was: sites.Snapshot)
        ├── sites.Page × N  (NEW: shared URL list, one record per URL)
        ├── lighthouse.Run  (was: lighthouse.Snapshot — status/config only)
        ├── headers.Run     (was: headers.Snapshot — status only)
        └── pageweight.Run  (was: pageweight.Snapshot — status only)

Per-tool results reference sites.Page (not a per-tool Page model):
  lighthouse.PageCategory  page = FK(sites.Page)
  lighthouse.PageAudit     page = FK(sites.Page)
  headers.PageData         page = FK(sites.Page)   (was: headers.Page)
  pageweight.PageData      page = FK(sites.Page)   (was: pageweight.Page)
  pageweight.Resource      page = FK(sites.Page)

Removed entirely:
  lighthouse.Page          (replaced by sites.Page)
  headers.Page             (replaced by sites.Page)
  pageweight.Page          (replaced by sites.Page)
  lighthouse.SnapshotCategory   (aggregation removed)
  lighthouse.SnapshotAudit      (aggregation removed)
```

The `Run` models are lean orchestration records: status, page_count, and any
tool-specific config (e.g. `lighthouse.Run` keeps `config_file`). They no longer
contain or own pages.

---

## API naming

API URLs change from `/snapshots/` to `/scans/`. The project is new with no external
consumers; now is the right time to make this change.

```
GET  /api/sites/{slug}/scans/
GET  /api/sites/{slug}/scans/latest/
POST /api/sites/{slug}/scans/
GET  /api/sites/{slug}/scans/{id}/
GET  /api/sites/{slug}/scans/{id}/pages/
GET  /api/sites/{slug}/scans/{id}/pages/{page_id}/
GET  /api/sites/{slug}/scans/{id}/lighthouse/pages/
GET  /api/sites/{slug}/scans/{id}/lighthouse/pages/{page_id}/
GET  /api/sites/{slug}/scans/{id}/headers/pages/
GET  /api/sites/{slug}/scans/{id}/pageweight/pages/
```

The shared page list is available at `/scans/{id}/pages/` — a clean answer to "which
URLs were included in this scan?" without having to pick a tool-specific endpoint.
Per-tool endpoints remain for tool-specific result detail.

---

## Stage 0 — Foundation refinements (current priority)

- **SQLite vs PostgreSQL**: Evaluate whether SQLite is sufficient. PostgreSQL handles
  concurrent Celery writes well; SQLite would reduce deployment friction. Decide before
  the deployment story solidifies.
- **Rename Snapshot → Scan throughout**: models, tasks, API, admin, tests, templates.
  This is a mechanical rename but touches every app. Do it as a single focused commit.
- **Introduce `sites.Page`**: add the shared page model, update the three existing
  tool result models to FK there, remove `lighthouse.Page`, `headers.Page`,
  `pageweight.Page`. Update tasks to create `sites.Page` records before dispatching
  per-tool work.
- **Remove pre-aggregation**: delete `SnapshotCategory`, `SnapshotAudit`, and the
  aggregation half of `collect_metrics()`. Move completion signalling into each
  `Run`'s completion task. Update the API to compute summaries on demand.
- **Stabilise Lighthouse audit IDs**: map Lighthouse-internal IDs to cricket-owned
  stable slugs in the collection task.
- Review and stabilise the existing three collectors.
- Improve test coverage on the API layer.
- Confirm the deployment story (Docker Compose, environment variables, first-run UX).
- Review `AGENTS.md` and `agent-context` for completeness and accuracy.

---

## Stage 1 — Per-tool enable flags and environment tagging

*These are prerequisites for all later stages.*

- **Per-tool enable flags on `sites.Site`**: `enable_lighthouse`, `enable_headers`,
  `enable_pageweight`, `enable_toolbar` (default `True` for existing tools, `False`
  for toolbar). `take_site_scan` checks each flag before dispatching.
- **Environment field on `sites.Scan`**: `environment` CharField (`local`, `staging`,
  `production`). Populated from `Site.extra_config["environment"]` at scan creation.
- **API**: `ScanOut` gains `environment`; `GET /scans/` gains `?environment=` filter;
  `agent-context` documents both.

Different collection cadences use separate `Site` objects with different crontabs and
different enable flags — not per-tool schedules on one Site.

---

## Stage 2 — Django Debug Toolbar integration

*Depends on Stage 1 (`enable_toolbar` flag).*

Detailed design in `docs/ddt-integration-plan.md`. That document uses old terminology
(Snapshot, per-tool Page models) — a translation note is at the top.

- New `apps/debugtoolbar/` collector. Follows the `headers` pattern.
- `debugtoolbar.Run` (status only) + `debugtoolbar.PageData` → FK(sites.Page).
- Requires companion package `django-cricket` installed in the target app.
- Development-only. Primary metric: SQL query count per page.
- `agent-context` must document all JSONField structures.

---

## Stage 3 — Multi-instance sync (local → shared server)

*Depends on Stage 1 (environment tagging).*

- **Push API endpoint**: `POST /api/sites/{slug}/scans/push/` (admin key required).
- **`push_scan` management command**: `--tools toolbar` pushes only DDT data.

Only push environment-independent data (DDT SQL counts, cache stats). Pageweight and
Lighthouse scores must be collected on the target environment, not pushed from local.

---

## Stage 4 — JS and CSS coverage

*Depends on Stage 0 (shared Page model). Extends the pageweight app.*

Chrome DevTools Protocol Coverage API, same Puppeteer session as pageweight.
Results stored in `pageweight.PageCoverage` → FK(sites.Page).

- Per-script/stylesheet: used bytes, unused bytes, coverage percentage.
- Per-function detail for non-minified builds; per-CSS-rule detail.
- Raw detail pruned on same schedule as DDT raw data.
- Key limitation: interaction-triggered code appears unused. Frame as "not executed
  during page load."

---

## Stage 5 — Cold/warm cache comparison

*Depends on Stage 0 (shared Page model). Extends the pageweight app.*

Second Puppeteer pass in the same collection task. Results in `pageweight.PageData`
as additional fields (warm_transfer_size, cache_saving_bytes, cache_saving_pct).

---

## Stage 6 — HTML validation

*Depends on Stage 0. New app following the headers pattern.*

W3C Nu Html Checker JSON API, one POST per page.
`htmlvalidation.Run` + `htmlvalidation.PageData` → FK(sites.Page).

- `error_count`, `warning_count` as scalar fields.
- Full message list in JSONField: `[{message, type, line, column}]`.

---

## Stage 7 — Broken link detection

*Depends on Stage 0. New app following the headers pattern.*

Per-page link extraction and HEAD request checking.
`linkcheck.Run` + `linkcheck.PageData` → FK(sites.Page).

- `broken_count`, `redirect_count` as scalar fields.
- Full link list in JSONField: `[{url, status_code, source_url}]`.
- JS-injected links need the Puppeteer session; static HTML needs only `requests`.

---

## Future ideas (no stage assigned)

**Carbon footprint estimate**
Derived from pageweight transfer size via the Website Carbon API. A computed field
on `pageweight.PageData`, no separate collection task needed.

**DNS and TLS analysis**
Per-domain rather than per-page. Overlaps with headers data. Revisit when security
auditing requirements are clearer.

**Rendered DOM snapshot**
Post-JS DOM capture for SSR/hydration mismatch detection. Niche; consider when there
is a specific need.

**First-party vs third-party resource breakdown**
Derivable from `pageweight.Resource` URL data at query time. Not a new collection task.

**Structured data validation**
Schema.org / Open Graph tag validation. Lighthouse covers some of this already.
