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


## Examples

Can show JSON diffs:

<details><summary><code>$ ganzua diff corpus/old-uv-project corpus/new-uv-project</code></summary>

```json
{
  "stat": {
    "total": 2,
    "added": 1,
    "removed": 0,
    "updated": 1
  },
  "packages": {
    "annotated-types": {
      "old": null,
      "new": {
        "version": "0.7.0",
        "source": "pypi"
      }
    },
    "typing-extensions": {
      "old": {
        "version": "3.10.0.2",
        "source": "pypi"
      },
      "new": {
        "version": "4.14.1",
        "source": "pypi"
      },
      "is_major_change": true
    }
  }
}
```

</details>

Can also show the diff as Markdown:

<details><summary><code>$ ganzua diff --format=markdown corpus/old-uv-project corpus/new-uv-project</code></summary>

```
2 changed packages (1 added, 1 updated)

| package           | old      | new    | notes |
|-------------------|----------|--------|-------|
| annotated-types   | -        | 0.7.0  |       |
| typing-extensions | 3.10.0.2 | 4.14.1 | (M)   |

* (M) major change
```

</details>

Here's the same diff in reverse, which now shows a `(D)` downgrade notice:

<details><summary><code>$ ganzua diff --format=markdown corpus/new-uv-project corpus/old-uv-project</code></summary>

```
2 changed packages (1 updated, 1 removed)

| package           | old    | new      | notes   |
|-------------------|--------|----------|---------|
| annotated-types   | 0.7.0  | -        |         |
| typing-extensions | 4.14.1 | 3.10.0.2 | (M) (D) |

* (M) major change
* (D) downgrade
```

</details>

The Markdown diff can show notices when the source of a package changes.
When multiple entries have the same note, their IDs are deduplicated:

<details><summary><code>$ ganzua diff --format=markdown corpus/sources-poetry corpus/sources-uv</code></summary>

```
6 changed packages (1 added, 5 updated)

| package            | old   | new   | notes |
|--------------------|-------|-------|-------|
| click              | 8.3.0 | 8.3.0 | (S1)  |
| click-example-repo | 1.0.0 | 1.0.0 | (S2)  |
| colorama           | 0.4.6 | 0.4.6 | (S1)  |
| idna               | 3.11  | 3.11  | (S1)  |
| propcache          | 0.4.1 | 0.4.1 | (S1)  |
| sources-uv         | -     | 0.1.0 |       |

* (S1) source changed from default to pypi
* (S2) source changed from <git+https://github.com/pallets/click.git@309ce9178707e1efaf994f191d062edbdffd5ce6#subdirectory=examples/repo> to <git+https://github.com/pallets/click.git@f67abc6fe7dd3d878879a4f004866bf5acefa9b4#subdirectory=examples/repo>
```

</details>

If there are no notes, the entire column is omitted:

<details><summary><code>$ ganzua diff --format=markdown corpus/new-uv-project corpus/minor-uv-project</code></summary>

```
1 changed packages (1 updated)

| package           | old    | new    |
|-------------------|--------|--------|
| typing-extensions | 4.14.1 | 4.15.0 |
```

</details>

When a there are no changes, the Markdown output omits the table:

<details><summary><code>$ ganzua diff --format=markdown corpus/new-uv-project corpus/new-uv-project</code></summary>

```
0 changed packages
```

</details>


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
