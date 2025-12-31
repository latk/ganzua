# ganzua diff

<!-- command output: ganzua help diff --markdown --markdown-links={slug}.md -->

Usage: `ganzua diff [OPTIONS] OLD NEW`

Compare two lockfiles.

The `OLD` and `NEW` arguments must each point to an `uv.lock` or `poetry.lock` file,
or to a directory containing such a file.

There is no direct support for comparing a file across Git commits,
but it's possible to retrieve other versions via [`git show`][git-show].
Here is an example using a Bash redirect to show non-committed changes in a lockfile:

```bash
ganzua diff <(git show HEAD:uv.lock) uv.lock
```

[git-show]: https://git-scm.com/docs/git-show

**Options:**

* `--format [json|markdown]`
  Choose the output format, e.g. Markdown. [default: json]
* `--help`
  Show this help message and exit.

<!-- command output end -->

## JSON Schema

Download: [schema.diff.json](schema.diff.json)

<!-- command output: ganzua schema diff --format=markdown -->

**Properties:**

* **`stat`**: [DiffStat](#type.DiffStat)
* **`packages`**: map(string → [DiffEntry](#type.DiffEntry))

### type `DiffStat` {#type.DiffStat}

**Properties:**

* **`total`**: int
* **`added`**: int
* **`removed`**: int
* **`updated`**: int

### type `DiffEntry` {#type.DiffEntry}

**Properties:**

* **`old`**: [LockedPackage](#type.LockedPackage) | null
* **`new`**: [LockedPackage](#type.LockedPackage) | null
* **`is_major_change`**?: bool\
  True if there was a major version change.

  This doesn't literally mean "the SemVer-major version component changed",
  but is intended to highlight version changes that are likely to have breakage.
* **`is_downgrade`**?: bool\
  True if the version was downgraded.
* **`is_source_change`**?: bool\
  True if the package source changed.

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
