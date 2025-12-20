# ganzua constraints bump

<!-- command output: ganzua help constraints bump --markdown --markdown-links=md-file -->

Usage: `ganzua constraints bump [OPTIONS] [PYPROJECT]`

Update `pyproject.toml` dependency constraints to match the lockfile.

Of course, the lockfile should always be a valid solution for the constraints.
But often, the constraints are somewhat relaxed.
This tool will *increment* the constraints to match the currently locked versions.
Specifically, the locked version becomes a lower bound for the constraint.

This tool will try to be as granular as the original constraint.
For example, given the old constraint `foo>=3.5` and the new version `4.7.2`,
the constraint would be updated to `foo>=4.7`.

The `PYPROJECT` argument should point to a `pyproject.toml` file,
or to a directory containing such a file.
If this argument is not specified,
the one in the current working directory will be used.

**Options:**

* `--lockfile PATH`
  Where to load versions from. Inferred if possible.
  * file: use the path as the lockfile
  * directory: use the lockfile in that directory
  * default: use the lockfile in the `PYPROJECT` directory
* `--backup PATH`
  Store a backup in this file.
* `--help`
  Show this help message and exit.

<!-- command output end -->
