# -*- makefile -*-

set shell := ["uv", "run", "bash", "-euo", "pipefail", "-c"]
set positional-arguments

# keep in sync with .github/workflows/test.yaml
[doc("run the entire QA suite")]
qa *args: sync lint types (test args) docs dist

# install dependencies if necessary
@sync:
  #!/usr/bin/env -S bash -euo pipefail
  uv sync
  uv run ./scripts/install-tools.py

# check formatting and code style
lint:
  ruff format --check --diff .
  ruff check .

# automatically fix formatting and some ruff violations
fix *files='.':
  #!/usr/bin/env -S uv run bash -euo pipefail
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
  mypy .

# run the test suite
test *args:
  pytest --cov=ganzua --cov=tests "$@"

# build wheel/sdist
dist:
    #!/usr/bin/env -S bash -euo pipefail
    set -euo pipefail

    echo "{{BOLD}}uv build{{NORMAL}}"
    uv build

    echo "{{BOLD}}running smoke tests{{NORMAL}}"
    ./scripts/par.py \
      uv run --isolated --no-sync --no-progress --with {} bash -c 'ganzua help >/dev/null' \
      ::: dist/ganzua-*.{whl,tar.gz}
    echo "{{BOLD}}all smoke tests succeeded{{NORMAL}}"

# serve a HTML page with code coverage on a random port
coverage-serve:
  coverage html
  python -m http.server -d htmlcov -b localhost 0

# perform a dependency upgrade using Ganzua
upgrade-deps:
  cp uv.lock old.uv.lock
  ganzua constraints reset --to=minimum --backup=old.pyproject.toml
  uv lock --upgrade  # perform the upgrade
  mv old.pyproject.toml pyproject.toml  # restore original constraints
  ganzua constraints bump
  uv lock
  ganzua diff --format=markdown old.uv.lock uv.lock
  rm old.uv.lock

# run an mdBook command
mdbook *args: sync
  ./scripts/mdbook "$@"

# run a lychee command
lychee *args: sync
  ./scripts/lychee "$@"

# Build the docs into `dist/docs` and check links.
docs: sync
  #!/usr/bin/env -S bash -euo pipefail
  ./scripts/mdbook build
  ./scripts/lychee --config lychee.toml --root-dir dist/docs --offline 'dist/docs/**/*.html'
