# API Design

An agent-native REST API for django-lighthouse, designed so that AI agents
can discover failing Lighthouse audits, understand what to fix, and verify
improvements — without ever running Lighthouse themselves.

The application is a **data store and cache**: it runs Lighthouse, stores the
structured results, and serves them in a form that is efficient to query.
Agents are the primary consumers; human browsing is secondary.

The design applies the 10 principles from
[Trevin Wisaksana's "10 Principles for Agent-Native CLIs"](https://trevinsays.com)
to an HTTP API context.  Every principle has a direct mapping: where the post
says "return JSON", the API says "consistent response envelope"; where it says
"--wait", the API says "webhook + job polling"; where it says "agent-context
subcommand", the API says `GET /api/agent-context/`.


## Contents

- [Guiding principles](#guiding-principles)
- [Data model](#data-model)
- [Endpoint map](#endpoint-map)
- [Response shapes](#response-shapes)
- [Error shapes](#error-shapes)
- [Async contract](#async-contract)
- [Introspection layers](#introspection-layers)
- [Primary agent workflows](#primary-agent-workflows)
- [Implementation plan](#implementation-plan)


---


## Guiding principles

### Tier 1 — Table stakes

#### 1. No ambiguous mutations

`POST /api/sites/{slug}/snapshots/` is idempotent.  If a snapshot is already
in-flight for the site the request returns the existing job rather than
starting a duplicate.  The response always carries `"existing": true/false`.
Forcing a new snapshot when one is already running requires an explicit
`"force": true` in the request body.

#### 2. Consistent response envelope

Every response — success and failure — uses the same outer shape.  Ratings are
always string slugs (`"poor"`, `"needs-improvement"`, `"good"`).  Scores are
always integers 0–100.  An agent reading the API never needs to know internal
storage details.

#### 3. Errors that enumerate valid values

When a filter value is rejected the error body names what is accepted:

```json
{
  "error": {
    "code": "invalid_rating",
    "message": "rating must be one of: poor, needs-improvement, good (got: \"bad\")",
    "field": "rating",
    "valid_values": ["poor", "needs-improvement", "good"]
  }
}
```

When a snapshot is already running the error points to the job:

```json
{
  "error": {
    "code": "snapshot_in_progress",
    "message": "A snapshot is already running. Poll the job for status, or pass \"force\": true to start a new one.",
    "job_id": 43,
    "poll_url": "/api/jobs/43/"
  }
}
```

#### 4. Safe retries — idempotent creation

`POST /api/sites/{slug}/snapshots/` returns the existing in-flight snapshot
with `"existing": true` rather than creating a duplicate.  Every mutation
response includes the resource ID.

#### 5. Bounded responses with teaching hints

Every list response includes `truncated`, `next_cursor`, and a `hint` that
tells the agent how to narrow the next query:

```json
{
  "items": [...],
  "count": 87,
  "limit": 20,
  "truncated": true,
  "next_cursor": "eyJpZCI6IDEyMDN9",
  "hint": "Add ?rating=poor to narrow to failing pages only"
}
```

Default `limit` is 20; maximum is 100.

---

### Tier 2 — Compounding

#### 6. Vocabulary consistency

- Resources: always plural nouns — `sites`, `snapshots`, `pages`, `jobs`, `audits`
- Actions: always `list` / `get` / `create`
- Filters: always `rating=`, always `category=`, always `audit=`
- IDs: slugs where natural (`my-site`, `largest-contentful-paint`), integers elsewhere
- Ratings: always the three string slugs everywhere

#### 7. Three-layer introspection

| Layer | Endpoint | Audience |
|-------|----------|----------|
| Hypermedia root | `GET /api/` | Human dropping in |
| Machine-readable schema | `GET /api/agent-context/` | Introspecting agent |
| OpenAPI 3.1 | `GET /api/schema/` | Tooling, SDK generation |

`agent-context` is a versioned JSON document budgeted to ≤ 800 tokens.  It
describes every endpoint, every filter parameter with its valid values, the
pagination convention, the async contract, and a link to `SKILLS.md`.

`SKILLS.md` is long-form prose describing how to accomplish the primary agent
workflows.  It describes tasks, not endpoints.

#### 8. Async-aware execution

The audit pipeline is inherently async — a snapshot for a large site can take
20–30 minutes.  `Snapshot.status` (`pending | running | complete | failed`) is
a first-class field.  `GET /api/jobs/{id}/` returns `retry_after` while
running and `result_url` when done.  Passing `webhook_url` on snapshot
creation receives a POST when the snapshot completes.

`GET /api/sites/{slug}/snapshots/latest/` is a shortcut to the most recent
*complete* snapshot — the most common thing an agent needs.

#### 9. Persistent identity — named API keys

A named `APIKey` model with a hashed secret and optional per-site scope.  The
key name appears in `agent-context` so the agent can verify its identity.

#### 10. Two-way I/O — webhooks and feedback

- `webhook_url` on snapshot creation routes the completed result to CI,
  another service, or a queue.
- `POST /api/feedback/` lets an agent report friction so maintainers learn
  about failures that would otherwise be silently retried.


---


## Data model

The application stores Lighthouse audit data in a fully normalised,
queryable schema.  There are no JSON blobs in the critical query path.

```
Site
  slug, name, url, config (Lighthouse flags), crontab, enabled
  current_snapshot → Snapshot   (FK, set on completion, O(1) "current state")

Snapshot
  site, status, platform, page_count
  config_file (temporary path, cleared after audit)

Page
  snapshot, url, audited
  report       (raw LHR JSON — pruned after 90 days)
  html_report  (self-contained HTML — permanent)

AuditDefinition          (~150 rows, upserted from LHR on each run)
  audit_id, category_id, title, description

PageCategory             (one row per category per audited page)
  page, category_id, score, rating

PageAudit                (one row per audit per audited page)
  page, audit → AuditDefinition
  score, rating, value, units, details (JSON — failing elements)

SnapshotCategory         (aggregate of PageCategory, one row per category per snapshot)
  snapshot, category_id, score, rating
  poor_count, needs_count, good_count

SnapshotAudit            (aggregate of PageAudit, one row per audit per snapshot)
  snapshot, audit → AuditDefinition
  poor_count, needs_count, good_count
```

**Retention policy:**
- Raw LHR JSON (`Page.report`) — pruned after 90 days by `prune_old_reports`
  management command and a weekly Celery beat task.  Structured data
  (PageAudit etc.) is retained indefinitely.
- HTML report (`Page.html_report`) — retained indefinitely.  Useful for human
  review and agent linking; cheap to serve, expensive to regenerate.

**No PDF reports.**  Reports are better generated by agents that can pull data
from multiple sources and tailor output to the audience.  The old report
generation code has been removed.


---


## Endpoint map

```
# Discovery & introspection
GET  /api/                                               Hypermedia root
GET  /api/agent-context/                                 Versioned schema + skill link
GET  /api/schema/                                        OpenAPI 3.1

# Audit definitions  (stable lookup, ~150 rows)
GET  /api/audits/                                        List all known audits
GET  /api/audits/{audit_id}/                             Audit title + description

# Sites  (read-only; configuration lives in the admin)
GET  /api/sites/                                         List sites
GET  /api/sites/{slug}/                                  Site detail

# Snapshots
GET  /api/sites/{slug}/snapshots/                        List, newest first, paginated
GET  /api/sites/{slug}/snapshots/latest/                 Most recent *complete* snapshot
POST /api/sites/{slug}/snapshots/                        Trigger audit (idempotent)
GET  /api/sites/{slug}/snapshots/{id}/                   Detail with SnapshotCategory scores

# Pages  (scoped to a snapshot)
GET  /api/sites/{slug}/snapshots/{id}/pages/             List; ?category=&rating=&audit=&limit=&cursor=
GET  /api/sites/{slug}/snapshots/{id}/pages/{id}/        PageAudit breakdown + AuditDefinition titles

# Jobs  (async tracking)
GET  /api/jobs/                                          In-flight and recent snapshots as jobs
GET  /api/jobs/{id}/                                     Status + retry_after + result_url

# Feedback
POST /api/feedback/                                      Agent reports friction
GET  /api/feedback/                                      List entries (admin key only)
```

Sites are read-only through the API.  Configuration (URL, sitemap, crontab,
Lighthouse config) belongs in the Django admin.


---


## Response shapes

### Site

```json
{
  "slug": "my-site",
  "name": "My Site",
  "url": "https://example.com",
  "enabled": true,
  "snapped": "2026-05-01T08:00:00Z",
  "crontab": "0 8 1 * *",
  "current_snapshot_id": 42
}
```

### Snapshot (summary, in a list)

```json
{
  "id": 42,
  "created": "2026-05-01T08:00:00Z",
  "status": "complete",
  "platform": "mobile",
  "page_count": 87,
  "categories": {
    "performance":    {"score": 74, "rating": "needs-improvement", "poor": 18, "needs": 51, "good": 18},
    "accessibility":  {"score": 91, "rating": "good",              "poor": 2,  "needs": 6,  "good": 79},
    "best-practices": {"score": 95, "rating": "good",              "poor": 0,  "needs": 4,  "good": 83},
    "seo":            {"score": 88, "rating": "needs-improvement", "poor": 5,  "needs": 40, "good": 42}
  }
}
```

### Snapshot (triggered / in-flight)

```json
{
  "id": 43,
  "status": "pending",
  "existing": false,
  "poll_url": "/api/jobs/43/",
  "webhook_url": "https://ci.example.com/lighthouse-hook"
}
```

### Page (in a list)

```json
{
  "id": 1203,
  "url": "https://example.com/about/",
  "audited": true,
  "html_report_url": "/audits/page/1203/report/",
  "categories": {
    "performance":   {"score": 61, "rating": "poor"},
    "accessibility": {"score": 100, "rating": "good"}
  }
}
```

### Page (detail)

The detail response joins `PageAudit` rows with `AuditDefinition` to give the
agent the human-readable title and description alongside the score.  The
`details` field contains Lighthouse's per-element failure data (which elements
have poor contrast, which images are too large, etc.) — exactly what an agent
needs to know *what to fix*, not just *that something is failing*.

```json
{
  "id": 1203,
  "url": "https://example.com/about/",
  "audited": true,
  "html_report_url": "/audits/page/1203/report/",
  "categories": {
    "performance": {"score": 61, "rating": "poor"}
  },
  "audits": {
    "largest-contentful-paint": {
      "title": "Largest Contentful Paint",
      "description": "Marks the time at which the largest text or image is painted.",
      "category": "performance",
      "score": 55,
      "rating": "poor",
      "value": 4200.0,
      "units": "millisecond",
      "details": {
        "type": "opportunity",
        "items": [{"url": "/images/hero.jpg", "totalBytes": 820000, "wastedMs": 1840}]
      }
    },
    "color-contrast": {
      "title": "Background and foreground colors have sufficient contrast",
      "description": "Low-contrast text is difficult or impossible for many users to read.",
      "category": "accessibility",
      "score": 100,
      "rating": "good",
      "value": null,
      "units": null,
      "details": null
    }
  }
}
```

### Audit definition

```json
{
  "audit_id": "largest-contentful-paint",
  "category_id": "performance",
  "title": "Largest Contentful Paint",
  "description": "Marks the time at which the largest text or image is painted. ..."
}
```

### Job

```json
{
  "id": 43,
  "kind": "snapshot",
  "status": "running",
  "started": "2026-05-28T16:00:00Z",
  "duration_s": 142,
  "retry_after": 30,
  "result_url": null
}
```

When complete:

```json
{
  "id": 43,
  "kind": "snapshot",
  "status": "complete",
  "started": "2026-05-28T16:00:00Z",
  "duration_s": 847,
  "retry_after": null,
  "result_url": "/api/sites/my-site/snapshots/43/"
}
```


---


## Error shapes

All errors use the same envelope.  Optional fields (`valid_values`, `poll_url`,
`field`) are present only when relevant.

```json
{
  "error": {
    "code": "invalid_category",
    "message": "category must be one of: performance, accessibility, best-practices, seo (got: \"ux\")",
    "field": "category",
    "valid_values": ["performance", "accessibility", "best-practices", "seo"]
  }
}
```

Standard error codes:

| Code | HTTP | Meaning |
|------|------|---------|
| `not_found` | 404 | Resource does not exist |
| `invalid_{field}` | 422 | Field value rejected; `valid_values` included |
| `snapshot_in_progress` | 409 | Snapshot running; `poll_url` included |
| `no_complete_snapshot` | 404 | `latest/` called but no complete snapshot exists |
| `no_html_report` | 404 | Page has no HTML report (pre-dates the feature) |
| `unauthorized` | 401 | Missing or invalid API key |
| `forbidden` | 403 | Key does not have access to this site |


---


## Async contract

```
POST /api/sites/my-site/snapshots/
Body: {"webhook_url": "https://ci.example.com/hook"}   # optional

→ 202 Accepted
  {"id": 43, "status": "pending", "existing": false, "poll_url": "/api/jobs/43/"}

# Option A — poll until done
GET /api/jobs/43/
→ {"status": "running", "retry_after": 30, "result_url": null}
# wait retry_after seconds and repeat

# Option B — receive webhook (preferred)
POST https://ci.example.com/hook
{
  "event": "snapshot.complete",
  "snapshot_id": 43,
  "site_slug": "my-site",
  "result_url": "/api/sites/my-site/snapshots/43/",
  "status": "complete"
}
```

If a snapshot is already in-flight and `force` is not set:

```
→ 409 Conflict
  {
    "error": {
      "code": "snapshot_in_progress",
      "message": "A snapshot is already running. Poll the job for status, or pass \"force\": true to start a new one.",
      "job_id": 43,
      "poll_url": "/api/jobs/43/"
    }
  }
```


---


## Introspection layers

### Layer 2 — agent-context (≤ 800 tokens)

```json
{
  "schema_version": "1",
  "api_key_name": "ci-pipeline",
  "base_url": "/api/",
  "resources": {
    "audits":    {"list": "GET /api/audits/", "get": "GET /api/audits/{audit_id}/"},
    "sites":     {"list": "GET /api/sites/", "get": "GET /api/sites/{slug}/"},
    "snapshots": {
      "list":    "GET /api/sites/{slug}/snapshots/",
      "latest":  "GET /api/sites/{slug}/snapshots/latest/",
      "create":  "POST /api/sites/{slug}/snapshots/",
      "get":     "GET /api/sites/{slug}/snapshots/{id}/"
    },
    "pages": {
      "list": "GET /api/sites/{slug}/snapshots/{id}/pages/",
      "get":  "GET /api/sites/{slug}/snapshots/{id}/pages/{id}/"
    },
    "jobs": {"list": "GET /api/jobs/", "get": "GET /api/jobs/{id}/"}
  },
  "filter_params": {
    "rating":   ["poor", "needs-improvement", "good"],
    "category": ["performance", "accessibility", "best-practices", "seo"],
    "status":   ["pending", "running", "complete", "failed"]
  },
  "pagination": {
    "cursor_param":  "cursor",
    "limit_param":   "limit",
    "default_limit": 20,
    "max_limit":     100
  },
  "async": {
    "trigger":  "POST to /snapshots/ returns 202 with poll_url immediately",
    "poll":     "GET /api/jobs/{id}/ until status is complete or failed; honour retry_after",
    "webhook":  "Pass webhook_url in POST body to receive a completion notification"
  },
  "feedback_url": "/api/feedback/",
  "skills_url":   "/docs/SKILLS.md"
}
```

### Layer 3 — SKILLS.md

Prose description of the primary agent workflows.  Sections:

1. Finding a site and reading its current scores
2. Locating failing pages for a specific category or audit
3. Reading audit detail to understand what to fix
4. Triggering a re-audit and waiting for results (poll or webhook)
5. Comparing scores before and after a fix
6. Delegating page fixes to a pool of agents
7. Identifying systemic issues across the portfolio
8. Reporting API friction via the feedback endpoint


---


## Primary agent workflows

### Fix the worst-performing pages for a specific audit

```
# 1. Find the site
GET /api/sites/
→ [{"slug": "my-site", ...}]

# 2. Check current scores
GET /api/sites/my-site/snapshots/latest/
→ performance: 61 (poor), accessibility: 91 (good)

# 3. Find the 10 worst pages for LCP
GET /api/sites/my-site/snapshots/42/pages/
    ?audit=largest-contentful-paint&rating=poor&limit=10
→ 10 pages, each with their LCP score

# 4. Get the full audit detail for one page
GET /api/sites/my-site/snapshots/42/pages/1203/
→ largest-contentful-paint: 4200ms (poor)
  details.items: [{"url": "/images/hero.jpg", "totalBytes": 820000}]
→ agent knows to optimise /images/hero.jpg

# 5. Fix and re-audit
POST /api/sites/my-site/snapshots/
{"webhook_url": "https://ci.example.com/hook"}
→ 202 {"id": 43, "poll_url": "/api/jobs/43/"}

# Webhook fires when done
→ GET /api/sites/my-site/snapshots/43/
  performance: 78 (needs-improvement) — improved from 61
```

### Identify systemic issues across the portfolio

The `PageAudit` table enables queries like "which audit fails most often across
all current snapshots?" without downloading any files.  Via the API this looks
like:

```
GET /api/audits/?has_failures=true&sort=fail_rate
→ [
    {"audit_id": "uses-optimized-images",  "fail_rate": 0.72, "failing_pages": 634},
    {"audit_id": "color-contrast",         "fail_rate": 0.61, "failing_pages": 538},
    {"audit_id": "largest-contentful-paint","fail_rate": 0.58, "failing_pages": 511}
  ]
```

This tells the team that image optimisation and colour contrast are systematic
weaknesses across the portfolio — not a problem unique to one site.

### Delegate to a pool of page-fix agents

```
# Orchestrator: get the worst 10 LCP pages
GET /api/sites/my-site/snapshots/42/pages/
    ?audit=largest-contentful-paint&rating=poor&limit=10
→ [page_1203, page_1204, ..., page_1212]

# For each page, delegate to a sub-agent with:
#   - the page URL
#   - GET /api/sites/my-site/snapshots/42/pages/{id}/ for full audit detail
#   - the raw LHR JSON at Page.report (available for 90 days) for correlated analysis
#
# The raw LHR is valuable because audits are correlated: slow LCP + large image
# + no lazy-loading + render-blocking resources may all share a single root cause
# that only becomes visible when analysing all the audit data together.
```


---


## Implementation plan

**Framework:** [Django Ninja](https://django-ninja.dev) — generates OpenAPI
from Python type hints, minimal boilerplate, integrates cleanly with the
existing Django and Celery setup.

**App name:** `lighthouse` (the `metrics` app has been renamed).

---

### Phase 1 — Foundation: auth and introspection

**New model:** `APIKey`
- `name` (CharField) — agent-readable identity shown in `agent-context`
- `key_prefix` (CharField) — first 8 chars, shown in admin
- `hashed_key` (CharField) — bcrypt hash, never the plaintext
- `created`, `last_used` (DateTimeField)
- `site` (FK to Site, nullable) — optional per-site scope

**New endpoints:**
- `GET /api/` — hypermedia root
- `GET /api/agent-context/` — versioned JSON document (≤ 800 tokens)
- `GET /api/schema/` — OpenAPI 3.1, auto-generated

**New file:** `docs/SKILLS.md`

---

### Phase 2 — Read endpoints

**Pydantic schema types** (defined once, used by all endpoints):
- `RatingSlug = Literal["poor", "needs-improvement", "good"]`
- `CategorySlug = Literal["performance", "accessibility", "best-practices", "seo"]`
- `PaginatedResponse[T]` — items, count, limit, truncated, next_cursor, hint

**New endpoints:** all `GET` endpoints from the map above.

The page detail endpoint joins `PageAudit` with `AuditDefinition` in a single
query so the agent receives title, description, score, rating, value, and
failure details in one response — no second call needed.

The audit list endpoint supports `?has_failures=true&sort=fail_rate` using
`SnapshotAudit` aggregated across all current snapshots.

---

### Phase 3 — Async-aware writes

**Updated `POST /api/sites/{slug}/snapshots/`:**
- Checks for `pending` or `running` snapshot → 409 unless `"force": true`
- Stores `webhook_url` on Snapshot
- Returns 202

**New Celery task:** `deliver_webhook(snapshot_pk)` — called from
`collect_metrics` when complete, and from the error link on failure.  POSTs
the snapshot status payload to `webhook_url` if set; retries 3× with
exponential backoff.

**New endpoints:**
- `GET /api/jobs/` — pending/running snapshots plus complete/failed within 24h
- `GET /api/jobs/{id}/` — status + `retry_after` + `result_url`

---

### Phase 4 — Feedback

**New model:** `APIFeedback` — text, created, api_key FK, endpoint

**New endpoints:**
- `POST /api/feedback/` — create; optionally forwards to `FEEDBACK_WEBHOOK_URL`
- `GET /api/feedback/` — list (admin key only)

---

### What each phase delivers

| Phase | Deliverable | Agent can… |
|-------|-------------|------------|
| 1 | Auth + introspection | Authenticate; discover the full API surface |
| 2 | Read endpoints | Read scores; find failing pages; get audit detail |
| 3 | Writes + jobs | Trigger audits; receive webhooks; poll jobs |
| 4 | Feedback | Report friction back to maintainers |
