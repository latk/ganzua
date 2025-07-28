# -*- makefile -*-

set shell := ["uv", "run", "bash", "-euo", "pipefail", "-c"]
set positional-arguments

# keep in sync with .github/workflows/test.yaml
[doc("run the entire QA suite")]
qa *args: sync lint types (test args) check-readme-up-to-date dist

# install dependencies if necessary
@sync:
  #!/bin/sh
  uv sync

# check formatting and code style
lint:
  ruff format --check --diff .
  ruff check .

# automatically fix formatting and some ruff violations
fix:
  ruff format .
  ruff check --fix-only --show-fixes .
  ./scripts/readme-usage.py update

# check types
types:
  mypy src tests

# run the test suite
test *args:
  pytest --cov=ganzua --cov=tests "$@"

# build wheel/sdist
dist:
    #!/usr/bin/env bash
    set -euo pipefail
    explicitly() { printf '%s' "{{BOLD}}running:{{NORMAL}}"; echo " ${@@K}"; "$@"; }  # print command before running

    explicitly uv build

    # run smoke tests for the build artifacts
    for dist in dist/ganzua-*.{whl,tar.gz}; do
      echo "{{BOLD}}running smoke test for ${dist}{{NORMAL}}"
      explicitly uv run --isolated --no-sync --with "$dist" bash -c 'ganzua help >/dev/null'
    done
    echo "{{BOLD}}all smoke tests succeeded{{NORMAL}}"

# serve a HTML page with code coverage on a random port
coverage-serve:
  coverage html
  python -m http.server -d htmlcov -b localhost 0

# check that the README is up to date with the CLI help
check-readme-up-to-date:
  ./scripts/readme-usage.py diff
