# ##########
#   System
# ##########
#
# Base image with OS-level dependencies, uv, and a non-root user.
# Shared by all subsequent stages.

FROM python:3.12-slim-bookworm AS system

WORKDIR /app

ARG UID=1000
ARG GID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libcairo2 libpango-1.0 \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
    && apt-get clean \
    && groupadd -g "${GID}" python \
    && useradd --create-home --no-log-init -u "${UID}" -g "${GID}" python \
    && chown python:python -R /app

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /usr/local/bin/uv

USER python

ENV LC_ALL="C.UTF-8" \
    PYTHONUNBUFFERED="true" \
    PYTHONPATH="/app/backend" \
    PATH="/app/.venv/bin:${PATH}" \
    VIRTUAL_ENV="/app/.venv" \
    TERM="xterm-256color" \
    USER="python"

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

WORKDIR /app/backend

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

COPY --chown=python:python . /app/backend

WORKDIR /app/backend

ENTRYPOINT ["/app/backend/bin/django-entrypoint"]

EXPOSE 8000

CMD ["gunicorn", "-c", "config/gunicorn.py", "config.wsgi"]
