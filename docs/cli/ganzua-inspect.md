# ganzua inspect

<!-- command output: ganzua help inspect --markdown --markdown-links=md-file -->

Usage: `ganzua inspect [OPTIONS] [LOCKFILE]`

Inspect a lockfile.

The `LOCKFILE` should point to an `uv.lock` or `poetry.lock` file,
or to a directory containing such a file.
If this argument is not specified,
the one in the current working directory will be used.

**Options:**

* `--format [json|markdown]`
  Choose the output format, e.g. Markdown. [default: json]
* `--help`
  Show this help message and exit.

<!-- command output end -->
