=================
Django Lighthouse
=================

Django Lighthouse automates website performance auditing using Google's
`Lighthouse <https://developer.chrome.com/docs/lighthouse/overview>`_.
It periodically crawls the pages of one or more sites, runs a full
Lighthouse audit on each page, aggregates the results into a snapshot, and
generates a PDF report — all without any manual intervention.

.. contents:: Table of contents
   :local:
   :depth: 2


Overview
--------

The workflow for each site is:

1. A **Site** record stores the URL, sitemap, Lighthouse configuration, and
   a crontab schedule.
2. Celery Beat polls for overdue sites every hour.  A site is overdue when
   the current time is past its next scheduled run.  Overdue sites receive a
   new **Snapshot**.
3. For each URL in the sitemap, a **Page** record is created and audited in
   parallel by running ``lighthouse.js`` in a headless Chrome subprocess.
4. Once all pages have been audited, per-page metrics are aggregated into the
   Snapshot (scores, ratings, quantile distributions).
5. A PDF report is generated and attached to the Snapshot.

Results are viewable in the Django admin and through the built-in report
views.  Snapshots taken at different times can be compared to track
improvements or regressions.


Features
--------

- Scheduled, fully automated audits driven by cron expressions.
- Mobile and desktop emulation (configurable per site).
- Four Lighthouse categories: **Performance**, **Accessibility**,
  **Best Practices**, and **SEO**.
- Per-page raw JSON reports kept on disk alongside aggregated snapshot data.
- PDF reports with score tables, rating distributions, and quantile charts.
- Django admin actions to trigger a snapshot manually at any time.
- Optional S3-compatible storage for media files.
- Celery Flower dashboard for monitoring task queues.
- Health-check endpoint via django-watchman.


Architecture
------------

.. code-block:: text

   ┌─────────────┐  hourly poll  ┌──────────────────────────────────────────┐
   │ Celery Beat │──────────────▶│ take_snapshots()                         │
   └─────────────┘               │   for each overdue site:                 │
                                │     take_snapshot()                       │
                                │       create_pages()                      │
                                │       audit_pages()  ─── audit_page() ×N  │
                                │       collect_metrics()                   │
                                │       publish_report()                    │
                                └───────────────────────────────────────────┘

Tasks run on two Celery queues:

- **sites** — snapshot orchestration (``take_snapshots``, ``take_snapshot``)
- **pages** — page-level work (``create_pages``, ``audit_page``, etc.)

The ``audit_page`` task executes ``node/src/lighthouse.js`` in a subprocess,
which launches headless Chrome and produces a JSON Lighthouse Result (LHR).
The Python layer then extracts the metrics it needs from that JSON.


Requirements
------------

- Python 3.12+
- Node.js 22 LTS
- PostgreSQL 17
- Redis 7.2
- Chrome / Chromium (present in the Docker image)
- Docker & Docker Compose (recommended for development)


Getting started
---------------

Clone the repository and copy the example environment file::

    git clone <repo-url> django-lighthouse
    cd django-lighthouse
    cp .env.example .env

All settings have sensible defaults for development, so no editing is
required before the first run.

Start the full stack::

    make up          # docker compose up -d

Wait a few seconds for the database to become healthy, then run migrations
and create an admin account::

    make migrate
    make createsuperuser

You can now open the Django admin at http://localhost:8000/admin/ and the
Celery Flower dashboard at http://localhost:5555.


Adding a site
-------------

1. Log in to the Django admin.
2. Open **Metrics → Sites → Add site**.
3. Fill in the required fields:

   - **Name** — a human-readable label.
   - **Slug** — auto-populated from the name; used in URLs.
   - **URL** — the site's homepage (used as a fallback if no sitemap is
     provided).
   - **Sitemap URL** or **Sitemap file** — one of these is needed so
     Lighthouse knows which pages to audit.  Leave both blank to audit the
     homepage only.
   - **Config** — optional JSON object of Lighthouse flags (see
     `Lighthouse configuration`_ below).
   - **Crontab** — a standard cron expression controlling how often automatic
     snapshots are taken.  Once a month is a typical cadence for tracking a
     project over the long term, e.g. ``0 8 1 * *`` to run at 08:00 on the
     first day of each month.  Use the admin action to trigger a snapshot
     manually whenever you need one outside the schedule.
   - **Enabled** — uncheck to pause audits without deleting the site.

4. Save.  The site will be audited automatically on its next scheduled run.

To trigger an immediate audit, select the site on the list page and choose
**Create snapshot** from the *Actions* dropdown.


Lighthouse configuration
------------------------

The **Config** JSON field on a Site is passed directly to Lighthouse as
CLI flags (minus ``formFactor``, which is handled specially — see below).
Leave it empty to use Lighthouse's built-in defaults.

**Emulation profiles**

+----------------------------------+-----------------------------+----------+
| Config                           | Profile                     | Default? |
+==================================+=============================+==========+
| ``{}``  or  ``{"formFactor":     | Mobile (Moto G Power).      | ✓        |
| "mobile"}``                      | 412 × 823 px.  Simulated    |          |
|                                  | slow 4G (150 ms RTT) and    |          |
|                                  | 4 × CPU throttle.           |          |
+----------------------------------+-----------------------------+----------+
| ``{"formFactor": "desktop"}``    | Desktop.  1350 × 940 px.    |          |
|                                  | Lighter throttle (40 ms     |          |
|                                  | RTT, 1 × CPU).              |          |
+----------------------------------+-----------------------------+----------+

**Other useful flags**

.. code-block:: json

    {
      "onlyCategories": ["performance", "accessibility"],
      "skipAudits": ["legacy-javascript"]
    }

See the `Lighthouse documentation <https://github.com/GoogleChrome/lighthouse/blob/main/docs/readme.md>`_
for a full list of supported flags.


Snapshots and reports
---------------------

A **Snapshot** records the state of a site's Lighthouse metrics at a point
in time.  Once all pages have been audited it holds:

- The per-category aggregate metrics (score, rating distribution, quantile
  histogram).
- The per-audit aggregate metrics (score distribution, pass/fail counts).
- A link to the pages that scored below the *Good* threshold (score < 90).
- A generated PDF report.

Snapshots are read-only in the admin.  They can only be created through the
task pipeline (automatically or via the admin action).

PDF reports are attached to the Snapshot and can also be downloaded from the
report detail view.


Development
-----------

The Makefile wraps the most common operations::

    make up              # start the stack
    make down            # stop the stack
    make build           # rebuild images after dependency changes
    make logs            # follow log output
    make shell           # open a Django shell_plus session
    make migrate         # run database migrations
    make makemigrations  # create new migrations (use app=<name> to target one)

**Updating Python dependencies**

Dependencies are managed with ``uv``::

    make lock            # regenerate uv.lock
    make build           # rebuild images to pick up the new lockfile


Code quality
------------

All checks run inside the Django container::

    make checks          # ruff lint + ruff format + mypy (all at once)
    make lint            # ruff lint only
    make format          # ruff format check only
    make mypy            # type checking only
    make fix             # auto-fix lint and formatting issues


Testing
-------

Tests are split into two categories:

**Unit tests** (fast, no browser required)::

    make tests           # default — runs everything except integration tests

**Integration tests** (slow, require Chrome, ~10–30 s each)::

    docker compose exec django pytest -m integration

    # or just the Node.js emulation-profile tests:
    docker compose exec django pytest -m integration tests/node/

**Coverage report**::

    make coverage        # generates an HTML report in ./coverage/

Test layout::

    tests/
    ├── factories/              # FactoryBoy factories for Site, Snapshot, Page
    ├── metrics/
    │   ├── conftest.py         # shared fixtures (lighthouse_report, page_data, …)
    │   ├── test_site.py        # SiteManager.overdue(), Site.create_snapshot()
    │   ├── test_snapshot.py    # Snapshot.create_pages(), collect_metrics()
    │   ├── test_page.py        # Page.audit(), metric extraction
    │   ├── test_sitemaps.py    # sitemap parsing
    │   └── test_snapshots.py   # end-to-end workflow (integration)
    └── node/
        └── test_lighthouse_js.py   # emulation & throttling profile tests (integration)


Environment variables
---------------------

All variables have working defaults for local development.  Copy
``.env.example`` to ``.env`` and uncomment any line you want to change.

Key variables:

+-------------------------------------+------------------------------------------------+
| Variable                            | Purpose                                        |
+=====================================+================================================+
| ``DJANGO_ENV``                      | ``development`` or ``production``              |
+-------------------------------------+------------------------------------------------+
| ``DJANGO_SECRET_KEY``               | Required in production                         |
+-------------------------------------+------------------------------------------------+
| ``DJANGO_ALLOWED_HOSTS``            | Comma-separated list of permitted hostnames    |
+-------------------------------------+------------------------------------------------+
| ``DATABASE_URL``                    | PostgreSQL connection string                   |
+-------------------------------------+------------------------------------------------+
| ``BROKER_URL``                      | Redis URL for Celery broker                    |
+-------------------------------------+------------------------------------------------+
| ``CACHE_URL``                       | Redis URL for Django cache                     |
+-------------------------------------+------------------------------------------------+
| ``CELERY_LOG_LEVEL``                | Celery worker log verbosity (default: debug)   |
+-------------------------------------+------------------------------------------------+
| ``AWS_ACCESS_KEY_ID`` etc.          | S3-compatible storage credentials (optional)   |
+-------------------------------------+------------------------------------------------+
| ``DJANGO_SENTRY_DSN``               | Sentry error tracking (optional)               |
+-------------------------------------+------------------------------------------------+
| ``DOCKER_POSTGRES_PORT_FORWARD``    | Expose Postgres on the host (e.g.              |
|                                     | ``127.0.0.1:5432``)                            |
+-------------------------------------+------------------------------------------------+
| ``DOCKER_REDIS_PORT_FORWARD``       | Expose Redis on the host                       |
+-------------------------------------+------------------------------------------------+
| ``DOCKER_FLOWER_PORT_FORWARD``      | Expose Flower on the host (default             |
|                                     | ``127.0.0.1:5555``)                            |
+-------------------------------------+------------------------------------------------+

See ``.env.example`` for the full list including Gunicorn tuning parameters.


Production notes
----------------

- Set ``DJANGO_ENV=production``, ``DJANGO_DEBUG=False``, and a strong
  ``DJANGO_SECRET_KEY``.
- Set ``DOCKER_RESTART_POLICY=unless-stopped`` in ``.env`` so all containers
  restart automatically.
- Configure ``DJANGO_ALLOWED_HOSTS`` with your real domain name.
- Point media storage at S3 or another durable store by setting
  ``DJANGO_DEFAULT_STORAGE_BACKEND`` and the ``AWS_*`` variables.
- Protect the health-check endpoint::

      DOCKER_DJANGO_HEALTHCHECK_TEST=curl -H "X-Watchman-Token: <token>" localhost:8000/watchman/ping
      DJANGO_WATCHMAN_TOKENS=<token>

- Scale auditing capacity by running additional Celery workers targeting the
  ``pages`` queue::

      celery -A config worker -Q pages --concurrency 4
