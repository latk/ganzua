# -*- makefile -*-

set shell := ["uv", "run", "bash", "-euo", "pipefail", "-c"]
set positional-arguments

qa *args: sync lint types (test args)

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

# check types
types:
  mypy src tests

# run the test suite
test *args:
  pytest --cov=lockinator --cov=tests "$@"

# serve a HTML page with code coverage on a random port
coverage-serve:
  coverage html
  python -m http.server -d htmlcov -b localhost 0
