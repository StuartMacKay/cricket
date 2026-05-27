FROM python:3.12-slim-bookworm AS app
LABEL maintainer="Stuart MacKay <smackay@flagstonesoftware.com>"

WORKDIR /app

# Install any os-level dependencies, clean out any unused files
# and create a user so nothing runs as root.

ARG UID=1000
ARG GID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libcairo2 libpango-1.0 \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
    && apt-get clean \
    && groupadd -g "${GID}" python \
    && useradd --create-home --no-log-init -u "${UID}" -g "${GID}" python \
    && chown python:python -R /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

USER python

# Install dependencies (leverages Docker layer caching — only reruns when
# pyproject.toml or uv.lock change)
COPY --chown=python:python pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project --no-group dev --no-group docs --no-group tests

# Set up the runtime environment

ARG DEBUG="false"
ENV DEBUG="${DEBUG}" \
    LC_ALL="C.UTF-8" \
    PYTHONUNBUFFERED="true" \
    PYTHONPATH="." \
    PATH="${PATH}:/app/.venv/bin" \
    TERM="xterm-256color" \
    USER="python" \
    VIRTUAL_ENV="/app/.venv"

# Copy over all the backend files and the static assets generated
# by the frontend tools/frameworks.
COPY --chown=python:python . ./backend
COPY --chown=python:python ../frontend/dist ./frontend/dist

# Use entrypoint and cmd so the command can be overridden from
# the command line.

ENTRYPOINT ["/app/backend/bin/django-entrypoint"]

EXPOSE 8000

CMD ["gunicorn", "-c", "/app/backend/config/gunicorn.py", "config.wsgi"]
