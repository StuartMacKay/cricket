#
# Makefile: Commands to simplify development and releases
#
# Usage:
#
#    make up          # start the full dev stack
#    make down        # stop the stack
#    make build       # (re)build images after dependency changes
#    make checks      # run all code checks inside the container
#    make tests       # run the test suite inside the container
#
# All targets that run code (tests, lint, manage commands) execute inside
# the running django container via `docker compose exec`. Run `make up`
# first, or prefix with: docker compose up -d

# This Makefile only works with GNU Make.

src_dirs = apps config

exec = docker compose exec django

# include additional targets or override variables from local makefiles
-include *.mk

.PHONY: help
help:
	@echo "The Makefile has the following targets..."
	@LC_ALL=C $(MAKE) -pRrq -f $(firstword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/(^|\n)# Files(\n|$$)/,/(^|\n)# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | grep -E -v -e '^[^[:alnum:]]' -e '^$@$$'

# #########
#   Clean
# #########

.PHONY: clean-tests
clean-tests:
	@echo "Deleting the pytest cache..."
	rm -rf .pytest_cache

.PHONY: clean-mypy
clean-mypy:
	@echo "Deleting the mypy cache..."
	rm -rf .mypy_cache

.PHONY: clean-coverage
clean-coverage:
	@echo "Deleting the coverage data and reports..."
	rm -rf .coverage
	rm -rf coverage

.PHONY: clean
clean: clean-coverage clean-mypy clean-tests

# ##########
#   Docker
# ##########

.PHONY: up
up:
	@echo "Starting the development stack..."
	docker compose up -d

.PHONY: down
down:
	@echo "Stopping the development stack..."
	docker compose down

.PHONY: build
build:
	@echo "Building images..."
	docker compose build

.PHONY: logs
logs:
	docker compose logs -f

.PHONY: ps
ps:
	docker compose ps

.PHONY: restart
restart:
	@echo "Restarting service (use svc=<name> to target one, e.g. make restart svc=django)..."
	docker compose restart $(svc)

# ################
#   Dependencies
# ################
#
# Updating dependencies is a local operation — it only needs the uv binary,
# not a project virtualenv. After running `make lock`, rebuild the images
# so containers pick up the new lockfile: `make build`

.PHONY: lock
lock:
	@echo "Update the lockfile..."
	uv lock

# ###########
#   Version
# ###########
#
# Version numbers follow semantic versioning (vMAJOR.MINOR.PATCH).
# bumpver updates pyproject.toml, commits the change, and tags the commit.
#
# Usage:
#   make bumpver             # increment patch (bug fixes: v0.1.0 → v0.1.1)
#   make bumpver tag=minor   # increment minor (new features: v0.1.0 → v0.2.0)
#   make bumpver tag=major   # increment major (breaking changes: v0.1.0 → v1.0.0)
#   make bumpver dry=1       # preview changes without committing

tag  ?= patch
dry  ?=

bumpver_flags = --$(tag)
ifneq ($(dry),)
bumpver_flags += --dry
endif

.PHONY: bumpver
bumpver:
	@echo "Bumping version ($(tag))$(if $(dry), [dry run],)..."
	@if [ -z "$(dry)" ]; then \
		NEW_VERSION=$$($(exec) bumpver update --$(tag) --dry 2>&1 | grep 'New Version' | awk '{print $$NF}'); \
		python3 bin/update-changelog $$NEW_VERSION; \
		git add CHANGELOG.rst; \
	fi
	$(exec) bumpver update $(bumpver_flags)

# ##########
#   Django
# ##########

.PHONY: migrate
migrate:
	@echo "Run any database migrations..."
	$(exec) python manage.py migrate

.PHONY: makemigrations
makemigrations:
	@echo "Create new database migrations..."
	$(exec) python manage.py makemigrations $(app)

.PHONY: createsuperuser
createsuperuser:
	$(exec) python manage.py createsuperuser

.PHONY: shell
shell:
	$(exec) python manage.py shell_plus

.PHONY: manage
manage:
	$(exec) python manage.py $(cmd)

# ##########
#   Checks
# ##########

.PHONY: lint
lint:
	@echo "Check the code for lint violations..."
	$(exec) ruff check $(src_dirs)

.PHONY: fix-lint
fix-lint:
	@echo "Fix lint violations automatically..."
	$(exec) ruff check --fix $(src_dirs)

.PHONY: format
format:
	@echo "Check the code for formatting violations..."
	$(exec) ruff format --check $(src_dirs)

.PHONY: fix-format
fix-format:
	@echo "Apply formatting..."
	$(exec) ruff format $(src_dirs)

.PHONY: fix
fix: fix-lint fix-format

.PHONY: mypy
mypy:
	@echo "Check the type annotations..."
	$(exec) mypy $(src_dirs)

.PHONY: checks
checks: lint format mypy
	@echo "Run all the code checks..."

# #########
#   Tests
# #########

.PHONY: coverage
coverage:
	@echo "Generate test coverage report..."
	$(exec) pytest --cov=apps --cov-report html

.PHONY: tests
tests:
	@echo "Run all the tests..."
	$(exec) pytest
