# Changelog

## Unreleased

## v0.2.0 (2025-09-11)

This release fixes some bugs that were found through real-world usage, adds convenience features like diff summaries, and implements new constraint edits.

Breaking changes:

* Renamed `ganzua constraints remove` to `ganzua constraints reset`.
* Schema change for `ganzua diff` JSON output: diff is nested under `packages` key.
* Schema change for `ganzua inspect` JSON output: data is nested under `packages` key to match the diff schema.

New features:

* New command `ganzua constraints inspect` lists all constraints in a `pyproject.toml` file, including extras, environment markers, and dependency groups. This is particularly helpful for debugging Ganzua.
* New option `ganzua constraints reset --to=minimum` edits constraints to require at least the currently locked version, while removing any previous constraints. Essentially, this makes all direct dependencies upgradeable.
* (https://github.com/latk/ganzua/issues/2) Add a summary line to `ganzua diff` Markdown output that counts the number of changes.
* Add a `stat` section to `ganzua diff` JSON output that counts the number of changes.

Fixes:

* Support loading lockfiles regardless of name. Previously, lockfiles had to be named `poetry.lock` or `uv.lock`.
* (https://github.com/latk/ganzua/issues/1) Support `pyproject.toml` files with out-of-order tables.

Other:

* Various internal changes. Improvements to `pyproject.toml` manipulation. Fewer special cases for Poetry.

Full Changelog: https://github.com/latk/ganzua/compare/v0.1.0...v0.2.0

## v0.1.0 (2025-08-16)

Initial release.

* add `ganzua inspect`
* add `ganzua diff`
* add `ganzua constraints bump`
* add `ganzua constraints remove`
