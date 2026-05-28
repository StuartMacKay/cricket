# ##########
#   System
# ##########
#
# Base image with OS-level dependencies, uv, Node.js, Chromium, and a
# non-root user. Shared by all subsequent stages.

FROM python:3.12-slim-bookworm AS system

WORKDIR /app

ARG UID=1000
ARG GID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
        libcairo2 libpango-1.0-0 libpangoft2-1.0-0 \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs chromium \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
    && apt-get clean \
    && groupadd -g "${GID}" python \
    && useradd --create-home --no-log-init -u "${UID}" -g "${GID}" python \
    && chown python:python -R /app \
    && mkdir /venv && chown python:python /venv

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /usr/local/bin/uv

USER python

ENV LC_ALL="C.UTF-8" \
    PYTHONUNBUFFERED="true" \
    PYTHONPATH="/app" \
    PATH="/venv/bin:${PATH}" \
    VIRTUAL_ENV="/venv" \
    UV_PROJECT_ENVIRONMENT="/venv" \
    TERM="xterm-256color" \
    USER="python" \
    CHROME_PATH="/usr/bin/chromium"

# ################
#   Dependencies
# ################
#
# Install production Python dependencies. This layer is cached as long as
# pyproject.toml and uv.lock are unchanged, even across app rebuilds.

FROM system AS dependencies

COPY --chown=python:python pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project --no-group dev --no-group docs --no-group tests

# ###############
#   Development
# ###############
#
# Extends the dependencies stage with dev/test tools. Source code is NOT
# copied here — it is mounted as a volume via docker-compose.override.yml
# so changes are reflected instantly without rebuilding.

FROM dependencies AS dev

RUN uv sync --frozen --no-install-project

COPY --chown=python:python node/ /app/node/

WORKDIR /app/node

RUN npm ci

WORKDIR /app

# ##############
#   Production
# ##############
#
# Final production image. Source code is baked in, only production
# dependencies are present.

FROM dependencies AS app

LABEL maintainer="Stuart MacKay <smackay@fastmail.com>"

ARG DEBUG="false"
ENV DEBUG="${DEBUG}"

COPY --chown=python:python . /app

COPY --chown=python:python node/ /app/node/

WORKDIR /app/node

RUN npm ci

WORKDIR /app

ENTRYPOINT ["/app/bin/django-entrypoint"]

EXPOSE 8000

CMD ["gunicorn", "-c", "config/gunicorn.py", "config.wsgi"]
