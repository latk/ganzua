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

## JSON Schema

Download: [schema.inspect.json](schema.inspect.json)

<!-- command output: ganzua schema inspect --format=markdown -->

**Properties:**

* **`packages`**: map(string → [LockedPackage](#type.LockedPackage))

### type `LockedPackage` {#type.LockedPackage}

**Properties:**

* **`version`**: string
* **`source`**: `pypi` | `default` | `other` | [SourceRegistry](#type.SourceRegistry) | [SourceDirect](#type.SourceDirect)

### type `SourceRegistry` {#type.SourceRegistry}

The package is sourced from a third party registry.

**Properties:**

* **`registry`**: string\
  URL or path to the registry.

### type `SourceDirect` {#type.SourceDirect}

The package is sourced from a specific URL or path, e.g. a Git repo or workspace path.

**Properties:**

* **`direct`**: string\
  URL or path to the package (directory or archive).
* **`subdirectory`**?: string | null\
  Only allowed if the source points to an archive file.

<!-- command output end -->
