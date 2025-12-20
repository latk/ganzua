# Command Line Reference

This section documents all Ganzua subcommands.

<!-- command output: ganzua help --markdown --subcommand-tree --markdown-links=md-file --subcommand-path -->

* [`ganzua`](ganzua.md)
  Inspect Python dependency lockfiles (uv and Poetry).
  * [`ganzua help`](ganzua-help.md)
    Show help for the application or a specific subcommand.
  * [`ganzua inspect`](ganzua-inspect.md)
    Inspect a lockfile.
  * [`ganzua diff`](ganzua-diff.md)
    Compare two lockfiles.
  * [`ganzua constraints`](ganzua-constraints.md)
    Work with `pyproject.toml` constraints.
    * [`ganzua constraints inspect`](ganzua-constraints-inspect.md)
      List all constraints in the `pyproject.toml` file.
    * [`ganzua constraints bump`](ganzua-constraints-bump.md)
      Update `pyproject.toml` dependency constraints to match the lockfile.
    * [`ganzua constraints reset`](ganzua-constraints-reset.md)
      Remove or relax any dependency version constraints from the `pyproject.toml`.
  * [`ganzua schema`](ganzua-schema.md)
    Show the JSON schema for the output of the given command.

<!-- command output end -->
