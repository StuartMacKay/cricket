# Agent Skills — Cricket API

This document describes how to accomplish primary tasks using the Cricket API.
Endpoint URLs, filter parameters, and response shapes are all described here.
Interactive API documentation is available at `/api/docs`.

---

## 1. Orienting: sites, runs, and pages

```
# List all sites you have access to
GET /api/sites/

# Get one site by slug
GET /api/sites/my-site/

# List runs for a site (newest first)
GET /api/sites/my-site/runs/

# Find the most recent complete run
GET /api/sites/my-site/runs/?status=complete&limit=1
```

A **Run** is one execution of a **Job**. A Job selects which audits to perform
and which pages to audit. Each run groups all per-page **Reports** for that
execution. Runs have status `running`, `complete`, or `failed`.

---

## 2. Reading current metrics for a site's pages

```
# List all pages Cricket has audited for a site
GET /api/sites/my-site/pages/

# Get the latest metrics for one page (from the most recent complete run)
GET /api/sites/my-site/pages/1203/metrics/

# Filter to metrics from one audit only
GET /api/sites/my-site/pages/1203/metrics/?audit=lighthouse

# Get metrics from a specific run
GET /api/sites/my-site/pages/1203/metrics/?run_id=42
```

The `/metrics/` response returns one `Metric` per `Definition` (measurable quantity).
Each Metric has `score` (0–100), `rating` (`poor`/`needs-improvement`/`good`),
`value`, `units`, and `measured` (timestamp).

Use `GET /api/definitions/` to discover all available metric definitions and their slugs.

---

## 3. Tracking a metric over time

```
# All recorded values for a specific metric, newest first
GET /api/sites/my-site/pages/1203/metrics/history/?definition=largest-contentful-paint

# All Lighthouse metrics across all runs for this page
GET /api/sites/my-site/pages/1203/metrics/history/?audit=lighthouse

# Limit the response
GET /api/sites/my-site/pages/1203/metrics/history/?definition=largest-contentful-paint&limit=10
```

The `measured` timestamp on each Metric mirrors the Run's `created` timestamp, so
records can be plotted as a time series without joining through the Run.

---

## 4. Reading raw report data

```
# List all reports in a run (one per page per audit)
GET /api/sites/my-site/runs/42/reports/

# Filter to one audit type
GET /api/sites/my-site/runs/42/reports/?audit=lighthouse

# Get the full report including raw data
GET /api/sites/my-site/runs/42/reports/5017/
```

The detail response includes `data` (structured JSON output from the audit task)
and, for Lighthouse, `json_report_url` and `html_report_url` (file download links).

Report data structure by audit type:

| Audit | `data` field |
|---|---|
| `lighthouse` | `{}` — data is in the JSON file at `json_report_url` |
| `page-headers` | `{status_code, headers: {}, redirect_count, final_url}` |
| `page-weight` | `{total_transfer_size, by_type: {document, script, image, …}}` |

---

## 5. Uploading findings from secondary processing

Agents can attach open-ended actionable items to a Report after secondary analysis:

```
POST /api/sites/my-site/runs/42/reports/5017/findings/
Authorization: Bearer <key>
Content-Type: application/json

{
  "type": "dead-link",
  "title": "Navigation link /old-page returns 404",
  "description": "Found in the main navigation menu.",
  "url": "https://my-site.example.com/old-page",
  "severity": "error",
  "source": "link-checker-agent"
}
```

The `type` field is a free slug — no pre-defined list. The page is derived from the
Report so you don't need to supply it. Use `source` to record which tool or agent
created the finding.

```
# Read findings for a page
GET /api/sites/my-site/pages/1203/findings/

# Filter by type, severity, or run
GET /api/sites/my-site/pages/1203/findings/?type=dead-link
GET /api/sites/my-site/pages/1203/findings/?severity=error
GET /api/sites/my-site/pages/1203/findings/?run_id=42
```

---

## 6. Comparing metrics before and after a fix

```
# Step 1: note the run that captured the baseline
GET /api/sites/my-site/runs/?status=complete&limit=1
# → run id=42, created=2026-06-01

# Step 2: wait for a new run to complete after deploying the fix
GET /api/sites/my-site/runs/?status=complete&limit=1
# → run id=45, created=2026-06-08

# Step 3: compare the same metric across both runs
GET /api/sites/my-site/pages/1203/metrics/?run_id=42
GET /api/sites/my-site/pages/1203/metrics/?run_id=45

# Or read the full history and slice it yourself
GET /api/sites/my-site/pages/1203/metrics/history/?definition=largest-contentful-paint
```

---

## 7. Identifying which pages have the worst metrics

```
# All recorded values for one definition across all pages — newest run per page
GET /api/sites/my-site/metrics/?definition=largest-contentful-paint

# Filter to pages rated "poor"
GET /api/sites/my-site/metrics/?definition=largest-contentful-paint&rating=poor
```

Results are sorted worst-first. Use cursor pagination to iterate over large sites:

```
GET /api/sites/my-site/metrics/?definition=largest-contentful-paint&rating=poor&limit=10
# → items + next_cursor

GET /api/sites/my-site/metrics/?definition=largest-contentful-paint&rating=poor&limit=10&cursor=<next_cursor>
```

---

## 8. Discovering available metric definitions

```
# List all registered Definitions
GET /api/definitions/

# Get one Definition (slug, name, description, audit, weight)
GET /api/definitions/largest-contentful-paint/
```

Definitions are created by the audit report processors and are the canonical list of
measurable quantities. Discover them via the API rather than hardcoding slugs — audit
tools change their metric names across versions and Cricket maps them to stable slugs.

---

## 9. Delegating page analysis across multiple agents

An orchestrator can partition pages or findings across worker agents using cursor
pagination:

```
# Get failing pages in batches of 10
GET /api/sites/my-site/metrics/?definition=largest-contentful-paint&rating=poor&limit=10
# → first batch + next_cursor

GET /api/sites/my-site/metrics/?definition=largest-contentful-paint&rating=poor&limit=10&cursor=<next_cursor>
# → second batch

# Each worker agent receives the page_url and can:
# - Read the full metric list for that page
GET /api/sites/my-site/pages/{id}/metrics/
# - Read raw report data (Lighthouse JSON, headers, etc.)
GET /api/sites/my-site/runs/{run_id}/reports/{report_id}/
# - Upload findings once analysis is done
POST /api/sites/my-site/runs/{run_id}/reports/{report_id}/findings/
```

---

## 10. Pagination

All list endpoints that may return large result sets use cursor pagination:

```json
{
  "items": [...],
  "count": 10,
  "limit": 20,
  "truncated": false,
  "next_cursor": "eyJpZCI6IDEyMH0",
  "hint": "..."
}
```

Pass `?cursor=<next_cursor>` to fetch the next page. When `truncated` is `false`
and `next_cursor` is `null`, you have reached the end. The `hint` field suggests
a narrower query when the result set is large.
