# -*- makefile -*-

set shell := ["uv", "run", "bash", "-euo", "pipefail", "-c"]
set positional-arguments

# keep in sync with .github/workflows/test.yaml
[doc("run the entire QA suite")]
qa *args: sync lint types (test args) check-readme-examples dist

# install dependencies if necessary
@sync:
  #!/bin/sh
  uv sync

# check formatting and code style
lint:
  ruff format --check --diff .
  ruff check .

# automatically fix formatting and some ruff violations
fix *files='.':
  #!/usr/bin/env -S uv run bash
  set -euo pipefail
  explicitly() { echo "{{BOLD}}${@@K}{{NORMAL}}" >&2; "$@"; }
  explicitly ruff format -- "$@"
  explicitly ruff check --fix-only --show-fixes -- "$@"
  if [[ "$*" == "." ]]; then
    explicitly ./scripts/par.py --shell \
      'ganzua schema {} >tests/schema.{}.json' \
      ::: diff inspect constraints-inspect
  fi

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
    echo "{{BOLD}}running smoke tests{{NORMAL}}"
    ./scripts/par.py \
      uv run --isolated --no-sync --no-progress --with {} bash -c 'ganzua help >/dev/null' \
      ::: dist/ganzua-*.{whl,tar.gz}
    echo "{{BOLD}}all smoke tests succeeded{{NORMAL}}"

# serve a HTML page with code coverage on a random port
coverage-serve:
  coverage html
  python -m http.server -d htmlcov -b localhost 0

# check that all shell examples in the README are up to date
check-readme-examples *args:
  TERM=dumb byexample --language shell README.md "$@"
