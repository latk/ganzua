# Changelog

<!-- INSTRUCTIONS:

- fill out the `Unreleased` section before a release
- if no `Unreleased` section exists, use the below template for new releases
- run `scripts/bump_version.py` to finalize an `Unreleased` section prior to tagging

TEMPLATE for new releases:

## Unreleased

Breaking changes:

New features:

Fixes:

Other:

Full diff: <https://github.com/latk/ganzua/compare/{last_release}...HEAD>

-->

## v0.4.0 (2026-04-11) {#v0.4.0}

This release brings fixes and quality-of-life improvements that were found through continued real-world usage.
This includes a new `--name` filter system, support for split versions, and information about which extras each constraint is part of.
Unfortunately, this required breaking changes to the JSON schema.

Breaking changes:

* Schema change for `ganzua inspect`: `packages` is now a list, not a dictionary.
  See “split versions” below.
  Previously, Ganzua would silently pick the last occurrence of each package.
  Now, all versions are shown, and no information is lost.
* Schema change for `ganzua constraints inspect`: renamed the `groups` JSON field to `in_groups`.

New features:

* Greatly improved docs and a new website at <https://ganzua.latk.de>.
  * The examples in the docs now serve as the primary test suite.
  * Each command that can output JSON now has an explicit output format specification.
* (<https://github.com/latk/ganzua/issues/6>) Add `--name=FILTER` to all commands that operate on lockfiles or constraints.
  This can be used to restrict which packages are included in the output,
  or which constraints are modified.
  Supports comma-separated package names, glob expressions, and gitignore-style exclusions, e.g. `--name 'foo*, !foo-bar'`.
* (<https://github.com/latk/ganzua/issues/5>) Support packages with “split versions”.
  When a lockfile contains solutions for multiple Python versions or other environment differences, there might not be a single package version that is compatible with all environments.
  Then, a lockfile might contain multiple versions for the same package.
  This is now handled properly in all commands that interact with lockfiles.
  Some operations like `ganzua constraints bump` will issue a warning when a package has an ambiguous version.
* Schema change for `ganzua constraints inspect`: track information about extras (optional dependencies) with a new `in_extras` field
* `ganzua constraints inspect`: show information about groups and extras in Markdown output
* Markdown output: hide certain columns if empty, e.g. “notes”.

Fixes:

* Sets are now shown in JSON output as sorted arrays.
  This ensures output remains stable across Ganzua runs.
* `ganzua constraints bump` now treats certain version constraint operators more sensibly.
  This was discovered while rewriting the tests as a specification document.
  * `===` arbitrary equality is now always updated, not removed.
  * Poetry `~` now behaves more like `>=` than like `~=`.
    This means a `~1` expression can now be handled correctly.

Other:

* Rewrote test suite to prefer CLI-level end-to-end tests over unit tests.

Full diff: <https://github.com/latk/ganzua/compare/v0.3.0...v0.4.0>

## v0.3.0 (2025-11-24) {#v0.3.0}

This release focuses on extracting information about package sources, but also includes quality-of-life improvements and bug fixes. There are no breaking changes.

New features:

* Arguments for `pyproject.toml` and lockfile paths are automatically inferred in the common cases where Ganzua is invoked from the project root. Instead of writing full paths, it is also sufficient to point to a directory containing these files. For example, `ganzua inspect`, `ganzua inspect .` and `ganzua inspect uv.lock` are generally equivalent.
* Keep some information about package sources (PyPI, Git, path dependencies, …) when inspecting lockfiles.
* Indicate certain kinds of differences that might need special attention in diff output (JSON/Markdown): `is_major_change` (M), `is_downgrade` (D), `is_source_change` (S).

Fixes:

* (<https://github.com/latk/ganzua/issues/3>) Normalize names of packages, extras, and dependency groups when loading `pyproject.toml` files, as required by the packaging specifications.
* (<https://github.com/latk/ganzua/issues/4>) Handle packages without versions in `uv.lock` files. The fake version `0+undefined` will be substituted instead.

Other:

* Run tests under Python 3.14.
* Added a `CHANGELOG.md` file.
* Various internal changes and testing improvements.

Full diff: <https://github.com/latk/ganzua/compare/v0.2.0...v0.3.0>


## v0.2.0 (2025-09-11) {#v0.2.0}

This release fixes some bugs that were found through real-world usage, adds convenience features like diff summaries, and implements new constraint edits.

Breaking changes:

* Renamed `ganzua constraints remove` to `ganzua constraints reset`.
* Schema change for `ganzua diff` JSON output: diff is nested under `packages` key.
* Schema change for `ganzua inspect` JSON output: data is nested under `packages` key to match the diff schema.

New features:

* New command `ganzua constraints inspect` lists all constraints in a `pyproject.toml` file, including extras, environment markers, and dependency groups. This is particularly helpful for debugging Ganzua.
* New option `ganzua constraints reset --to=minimum` edits constraints to require at least the currently locked version, while removing any previous constraints. Essentially, this makes all direct dependencies upgradeable.
* (<https://github.com/latk/ganzua/issues/2>) Add a summary line to `ganzua diff` Markdown output that counts the number of changes.
* Add a `stat` section to `ganzua diff` JSON output that counts the number of changes.

Fixes:

* Support loading lockfiles regardless of name. Previously, lockfiles had to be named `poetry.lock` or `uv.lock`.
* (<https://github.com/latk/ganzua/issues/1>) Support `pyproject.toml` files with out-of-order tables.

Other:

* Various internal changes. Improvements to `pyproject.toml` manipulation. Fewer special cases for Poetry.

Full diff: <https://github.com/latk/ganzua/compare/v0.1.0...v0.2.0>


## v0.1.0 (2025-08-16) {#v0.1.0}

Initial release.

* add `ganzua inspect`
* add `ganzua diff`
* add `ganzua constraints bump`
* add `ganzua constraints remove`
