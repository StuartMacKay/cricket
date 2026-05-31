# Decision Log

A running record of significant changes to the project and why they were made.
Not exhaustive — the bar is "would a future developer or agent look at this and
wonder why?" If yes, log it. If it's obvious from the code, skip it.

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

### Documentation pattern established

Three documents, three jobs:
- `AGENTS.md` — current state of the project. Always reflects what exists now.
- `docs/development-plan.md` — what is yet to be built, in order. Living document.
- `docs/decisions.md` — this file. What changed and why, in chronological order.
  Append-only; gaps are acceptable; the bar is "would this be confusing without
  an explanation?"
