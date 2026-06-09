# Cricket 🦗

Cricket is a web quality auditing server. It runs Google Lighthouse, HTTP header
checks, and Puppeteer-based page-weight measurements across one or more sites on
a cron schedule, stores the results in SQLite, and exposes everything through an
agent-native REST API.

## What it does

| Audit | Tool | What it measures |
|---|---|---|
| `lighthouse` | Google Lighthouse 13 | Performance, Accessibility, Best Practices, SEO |
| `page-headers` | Python `requests` | HTTP response headers (security, caching, redirects) |
| `page-weight` | Puppeteer | Transfer size by resource type |

Each audit type is registered as an **Audit** record. A **Job** selects a Site, a
set of Audits (e.g. Lighthouse + page-headers), and the pages to audit — either
discovered from a sitemap or supplied as an explicit URL list. Each Job execution
creates a **Run** that tracks progress and groups all per-page **Reports**.

Scalar measurements (LCP, FID, transfer size) are extracted from Reports and stored
as **Metrics** for trend analysis. Open-ended actionable items (broken links, large
images) are stored as **Findings**, which can also be uploaded via the API by agents.

## Stack

- **Python 3.12** · Django 6 · Django Ninja (REST API)
- **Celery + Redis** — task queue and broker
- **SQLite** — primary store
- **Node.js 22 LTS** — Lighthouse 13 + Puppeteer
- **Docker + Docker Compose** — development and production

## Getting started

```bash
git clone <repo-url> cricket
cd cricket
make develop
```

`make develop` installs pre-commit hooks, copies `.env.example` to `.env`,
copies `docker-compose.override.yml.example` to `docker-compose.override.yml`,
starts the Docker stack, runs migrations, and seeds a demo admin account,
site, job, and API key. The API key is printed at the end.

`docker-compose.override.yml` configures the local development stack: it
mounts your source tree into the containers, exposes ports, and targets the
`dev` image stage so code changes are picked up without a rebuild. Edit it to
customise your local environment — Docker Compose merges it automatically with
`docker-compose.yml`, and it is git-ignored so your changes stay local.

- Admin: <http://localhost:8000/admin/> — `admin` / `password`
- Flower: <http://localhost:5555>
- API: `Authorization: Bearer <key printed by make develop>`

Individual steps are also available as separate targets if you need to re-run
them:

| Target | What it does |
|---|---|
| `make admin` | Create the `admin` superuser (idempotent) |
| `make demo` | Create the example.com site and job (idempotent) |
| `make apikey` | Print the dev API key, write it to `.env` as `CRICKET_API_KEY` |
| `make secretkey` | Generate a new Django secret key, write it to `.env` as `DJANGO_SECRET_KEY` |

## Adding a site and running an audit

### 1. Create a Site

In the admin: **Audits → Sites → Add site**.

Fill in **Name**, **Slug**, **URL**, and optionally **Environment**
(`local`, `staging`, or `production`). Use separate Site records for different
environments of the same project — Lighthouse scores from a local machine and from
staging are not comparable.

### 2. Create a Job

In the admin: **Audits → Jobs → Add job**.

- Select the **Site**.
- Select one or more **Audits** (e.g. Lighthouse, page-headers).
- Supply the pages to audit: paste sitemap URLs into **Sitemaps** (one per line)
  or an explicit list of page URLs into **URLs** (one per line).
- Set a **Schedule** (crontab, e.g. `0 8 1 * *` for 08:00 on the first of each
  month). Leave blank for a manual-only Job.
- Choose a **Device** (`mobile` or `desktop`) and check **Enabled**.

To trigger an immediate run, select the Job in the admin and use the
**Trigger run** action.

### 3. Create an API key

In the admin: **Api → Api keys → Add api key**. Give it a name and save. Use
the generated key as a Bearer token: `Authorization: Bearer <key>`.

Or from the command line: `make apikey`.

## API

The API is agent-native: Bearer auth and cursor pagination throughout.

```
GET  /api/sites/
GET  /api/sites/{slug}/

GET  /api/sites/{slug}/jobs/
GET  /api/sites/{slug}/jobs/{id}/

GET  /api/sites/{slug}/runs/
GET  /api/sites/{slug}/runs/{id}/
GET  /api/sites/{slug}/runs/{id}/reports/
GET  /api/sites/{slug}/runs/{id}/reports/{id}/
POST /api/sites/{slug}/runs/{id}/reports/{id}/findings/

GET  /api/sites/{slug}/pages/
GET  /api/sites/{slug}/pages/{id}/
GET  /api/sites/{slug}/pages/{id}/metrics/
GET  /api/sites/{slug}/pages/{id}/metrics/history/
GET  /api/sites/{slug}/pages/{id}/findings/

GET  /api/sites/{slug}/metrics/
GET  /api/definitions/
GET  /api/definitions/{slug}/
```

Interactive docs are available at `/api/docs`.

## Development

```bash
make up              # start the stack
make down            # stop the stack
make build           # rebuild images after dependency changes
make logs            # follow log output
make shell           # open a Django shell_plus session
make migrate
make tests           # run the test suite
make checks          # ruff lint + format + mypy
make coverage        # HTML coverage report in ./coverage/

make admin           # create admin superuser (idempotent)
make demo            # create example.com site and job (idempotent)
make apikey          # print dev API key, write to .env as CRICKET_API_KEY
make secretkey       # generate secret key, write to .env as DJANGO_SECRET_KEY
```

## Environment variables

All variables have working defaults for local development. `make develop`
copies `.env.example` to `.env` automatically — uncomment only what you need
to change.

**Required in development and production:**

| Variable                 | Purpose                                                 |
|--------------------------|---------------------------------------------------------|
| `DJANGO_ENV`             | Set to `development` to `production`                    |
| `DJANGO_SECRET_KEY`      | Secret key — can be any string for development          |
| `DJANGO_ALLOWED_HOSTS`   | Comma-separated permitted hostnames                     |
| `DJANGO_WATCHMAN_TOKENS` | Protect the health check endpoint; comma-separated list |

**Optional:**

| Variable            | Purpose                                                                       |
|---------------------|-------------------------------------------------------------------------------|
| `DJANGO_DEBUG`      | Enable debugging; defaults to `False` (startup fails in production if `True`) |
| `DJANGO_LOG_LEVEL`  | Log verbosity; defaults to `INFO`                                             |
| `DJANGO_SENTRY_DSN` | Sentry error tracking; defaults to empty string, disabling Sentry             |
| `CELERY_LOG_LEVEL`  | Log verbosity for Celery; defaults to `warning`                               |

**Gunicorn:**

The default values for configuring gunicorn are sufficient for development only.

| Variable                     | Purpose                                                                                                 |
|------------------------------|---------------------------------------------------------------------------------------------------------|
| `GUNICORN_NUMBER_OF_WORKERS` | Worker processes; default 1, increase in production: 2 * cpus + 1                                       |
| `GUNICORN_NUMBER_OF_THREADS` | Threads per worker processes; default 1, increase in production                                         |
| `GUNICORN_MAX_REQUESTS`      | Number of requests before restarting worker: 0 in development (disabled); 1000 or similar in production |
| `GUNICORN_TIMEOUT`           | Number of seconds before request times out. default = 3                                                 |
| `GUNICORN_RELOAD`            | Restart worker on code change: True for development; False for production                               |
| `GUNICORN_LOG_LEVEL`         | Log verbosity; defaults to `debug`                                                                      |
