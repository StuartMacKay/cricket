# Agent Skills — Cricket API

This document describes how to accomplish the primary tasks using the
Cricket API.  Read `GET /api/agent-context/` first to confirm
endpoint URLs and filter parameters for the version you are talking to.

---

## 1. Finding a site and reading its current scores

```
# List all sites you have access to
GET /api/sites/

# Get one site by slug
GET /api/sites/my-site/

# Read the most recent complete snapshot (O(1) — no scanning)
GET /api/sites/my-site/snapshots/latest/
```

The `latest/` response includes `categories` with aggregated scores and
poor/needs/good page counts for each category.  If no complete snapshot
exists yet the response is 404 with code `no_complete_snapshot`.

---

## 2. Locating failing pages for a specific category or audit

```
# All pages with a "poor" accessibility rating
GET /api/sites/my-site/snapshots/42/pages/
    ?category=accessibility&rating=poor

# All pages that fail a specific audit
GET /api/sites/my-site/snapshots/42/pages/
    ?audit=largest-contentful-paint&rating=poor

# Combine: poor LCP pages, 10 at a time, ordered by URL
GET /api/sites/my-site/snapshots/42/pages/
    ?audit=largest-contentful-paint&rating=poor&limit=10

# Next page using cursor from previous response
GET /api/sites/my-site/snapshots/42/pages/
    ?audit=largest-contentful-paint&rating=poor&limit=10&cursor=<next_cursor>
```

The `hint` field in each list response suggests narrowing parameters if
the result set is large.

---

## 3. Reading audit detail to understand what to fix

```
GET /api/sites/my-site/snapshots/42/pages/1203/
```

The response joins `PageAudit` with `AuditDefinition` so you receive the
human-readable `title` and `description` alongside `score`, `rating`,
`value`, and `details` (the per-element failure data) in a single call.

The `details` field is Lighthouse's raw audit detail section.  For image
audits it lists individual images with their `url`, `totalBytes`, and
`wastedMs`.  For contrast audits it lists failing elements with their
CSS selectors.  This is what you need to know *what to fix*, not just
*that something is failing*.

---

## 4. Triggering a re-audit and waiting for results

### Option A — Poll

```
# Trigger a new snapshot
POST /api/sites/my-site/snapshots/
{}

# Response: 202 Accepted
# {"id": 43, "status": "pending", "poll_url": "/api/jobs/43/"}

# Poll until done (honour retry_after)
GET /api/jobs/43/
# → {"status": "running", "retry_after": 30, "result_url": null}
# wait 30 seconds
GET /api/jobs/43/
# → {"status": "complete", "result_url": "/api/sites/my-site/snapshots/43/"}

# Read the results
GET /api/sites/my-site/snapshots/43/
```

### Option B — Webhook (preferred for long-running audits)

```
POST /api/sites/my-site/snapshots/
{"webhook_url": "https://your-service.example.com/lighthouse-hook"}

# Your service receives a POST when the snapshot completes:
# {
#   "event": "snapshot.complete",
#   "snapshot_id": 43,
#   "site_slug": "my-site",
#   "result_url": "/api/sites/my-site/snapshots/43/",
#   "status": "complete"
# }
```

### If a snapshot is already running

```
# 409 Conflict
# {"error": {"code": "snapshot_in_progress", "job_id": 43, "poll_url": "/api/jobs/43/"}}

# Force a new one anyway
POST /api/sites/my-site/snapshots/
{"force": true}
```

---

## 5. Comparing scores before and after a fix

```
# Before fix: snapshot 42
GET /api/sites/my-site/snapshots/42/
# → performance: 61 (poor)

# After fix: trigger and wait for snapshot 43
POST /api/sites/my-site/snapshots/
# → wait for completion

GET /api/sites/my-site/snapshots/43/
# → performance: 78 (needs-improvement) — improved

# Compare a specific page
GET /api/sites/my-site/snapshots/42/pages/1203/
GET /api/sites/my-site/snapshots/43/pages/<new-page-id>/
# → largest-contentful-paint: 4200ms → 1800ms
```

---

## 6. Delegating page fixes to a pool of agents

An orchestrator agent can partition failing pages across worker agents:

```
# Get the worst 20 LCP pages (two workers of 10 each)
GET /api/sites/my-site/snapshots/42/pages/
    ?audit=largest-contentful-paint&rating=poor&limit=10
# → first 10 pages + next_cursor

GET /api/sites/my-site/snapshots/42/pages/
    ?audit=largest-contentful-paint&rating=poor&limit=10&cursor=<next_cursor>
# → next 10 pages

# Each worker agent receives:
# - The page URL (to edit the source)
# - GET /api/.../pages/{id}/ for the full audit detail (what to fix)
# - The raw LHR JSON is at Page.report (available for 90 days) for
#   correlated analysis when multiple audits share a root cause
```

---

## 7. Identifying systemic issues across the portfolio

```
# Which audits fail most often across all sites?
GET /api/audits/?has_failures=true&sort=fail_rate
# → [
#     {"audit_id": "uses-optimized-images", "fail_rate": 0.72, "failing_pages": 634},
#     {"audit_id": "color-contrast",        "fail_rate": 0.61, "failing_pages": 538}
#   ]
```

This uses `SnapshotAudit` aggregated across all current snapshots — no
file downloads, no scanning.

---

## 8. Reporting API friction via the feedback endpoint

If an endpoint returns an unexpected result or you hit a gap in the API,
report it so maintainers can improve the service:

```
POST /api/feedback/
{
  "endpoint": "GET /api/sites/my-site/snapshots/42/pages/",
  "message": "The ?audit= filter doesn't work when combined with ?category=. Expected intersection; got empty result."
}
```

Feedback is stored against your API key and is visible to admins at
`GET /api/feedback/`.
