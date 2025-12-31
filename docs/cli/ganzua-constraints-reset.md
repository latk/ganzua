# ganzua constraints reset

<!-- command output: ganzua help constraints reset --markdown --markdown-links={slug}.md -->

Usage: `ganzua constraints reset [OPTIONS] [PYPROJECT]`

Remove or relax any dependency version constraints from the `pyproject.toml`.

This can be useful for allowing uv/Poetry to update to the most recent versions,
ignoring the previous constraints. Approximate recipe:

```bash
ganzua constraints reset --to=minimum --backup=pyproject.toml.bak
uv lock --upgrade  # perform the upgrade
mv pyproject.toml.bak pyproject.toml  # restore old constraints
ganzua constraints bump
uv lock
```

The `PYPROJECT` argument should point to a `pyproject.toml` file,
or to a directory containing such a file.
If this argument is not specified,
the one in the current working directory will be used.

**Options:**

* `--backup PATH`
  Store a backup in this file.
* `--to [none|minimum]`
  How to reset constraints.
  * `none` (default): remove all constraints
  * `minimum`: set constraints to the currently locked minimum, removing upper bounds
* `--lockfile PATH`
  Where to load current versions from (for `--to=minimum`). Inferred if possible.
  * file: use the path as the lockfile
  * directory: use the lockfile in that directory
  * default: use the lockfile in the `PYPROJECT` directory
* `--help`
  Show this help message and exit.

<!-- command output end -->
