# Cricket 🦗

Cricket is a web quality auditing server. It runs Google Lighthouse, HTTP
header checks, and Puppeteer-based page-weight measurements across one or
more sites on a cron schedule, stores the results in PostgreSQL, and exposes
everything through an agent-native REST API.

## What it does

| App | Tool | What it measures |
|---|---|---|
| `lighthouse` | Google Lighthouse 13 | Performance, Accessibility, Best Practices, SEO |
| `headers` | Python `requests` | HTTP response headers (security, caching, redirects) |
| `pageweight` | Puppeteer | Transfer size by resource type |

Every audit is attached to a **Site** (a URL + sitemap + cron schedule).
Running an audit creates a **Snapshot** that groups all the per-page results
at that point in time. Snapshots can be compared to track improvements or
regressions over time.

## Stack

- **Python 3.12** · Django 6 · Django Ninja (REST API)
- **Celery + Redis** — task queue and broker
- **PostgreSQL 17** — primary store
- **Node.js 22 LTS** — Lighthouse 13 + Puppeteer
- **Docker + Docker Compose** — development and production

## Getting started

```bash
git clone <repo-url> cricket
cd cricket
make setup          # install pre-commit hooks

cp .env.example .env
make up             # docker compose up -d
make migrate
make createsuperuser
```

Open the Django admin at <http://localhost:8000/admin/> and the Celery Flower
dashboard at <http://localhost:5555>.

## Adding a site

1. Log in to the admin and open **Lighthouse → Sites → Add site**.
2. Fill in **Name**, **Slug**, **URL**, and optionally a **Sitemap URL** or
   **Sitemap file** (leave both blank to audit the homepage only).
3. Choose a **Platform** — `mobile` (default) or `desktop`.
4. Set a **Crontab** schedule, e.g. `0 8 1 * *` to run at 08:00 on the first
   day of each month.
5. Check **Enabled** and save.

To trigger an immediate audit, select the site and choose **Create snapshot**
from the *Actions* dropdown, or `POST /api/sites/{slug}/snapshots/`.

## API

The API is agent-native: Bearer auth, cursor pagination, 202 async with
webhooks, and a machine-readable context document at `GET /api/agent-context/`.

```
GET  /api/sites/
GET  /api/sites/{slug}/
GET  /api/sites/{slug}/snapshots/
GET  /api/sites/{slug}/snapshots/latest/
POST /api/sites/{slug}/snapshots/
GET  /api/sites/{slug}/snapshots/{id}/
GET  /api/sites/{slug}/snapshots/{id}/pages/
GET  /api/sites/{slug}/snapshots/{id}/pages/{page_id}/
GET  /api/audits/
GET  /api/jobs/{id}/
POST /api/feedback/
```

Full usage examples are in [`docs/SKILLS.md`](docs/SKILLS.md).

## Development

```bash
make up              # start the stack
make down            # stop the stack
make build           # rebuild images after dependency changes
make logs            # follow log output
make shell           # open a Django shell_plus session
make migrate
make tests           # unit tests (fast)
make checks          # ruff lint + format + mypy
make coverage        # HTML coverage report in ./coverage/
```

Integration tests require Chrome and are skipped by default:

```bash
docker compose exec django pytest -m integration
```

## Environment variables

All variables have working defaults for local development. Copy `.env.example`
to `.env` and edit as needed. Key variables:

| Variable | Purpose |
|---|---|
| `DJANGO_ENV` | `development` or `production` |
| `DJANGO_SECRET_KEY` | Required in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated permitted hostnames |
| `DATABASE_URL` | PostgreSQL connection string |
| `BROKER_URL` | Redis URL for Celery broker |
| `CACHE_URL` | Redis URL for Django cache |
| `AWS_ACCESS_KEY_ID` etc. | S3-compatible storage (optional) |
| `DJANGO_SENTRY_DSN` | Sentry error tracking (optional) |
