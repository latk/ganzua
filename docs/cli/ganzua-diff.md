# ganzua diff

<!-- command output: ganzua help diff --markdown --markdown-links={slug}.md -->

Usage: `ganzua diff [OPTIONS] [OLD] [NEW]`

Compare two lockfiles.

The `OLD` and `NEW` arguments can be any of the following:

* file: use that path as the lockfile (e.g. `uv.lock` or `poetry.lock`)
* directory: look for a lockfile in that directory
* git blob: a `<commit>:<path>` identifying a lockfile in the Git history

Here's an example of using the Git feature to show non-committed changes in a lockfile:

```bash
ganzua diff HEAD:uv.lock uv.lock
```

Depending on whether `--git`, `OLD`, and `NEW` are present,
Lockfile data may be loaded from the Git history.

* `ganzua diff <lockfile> <lockfile>` compares two lockfiles,
  each of which may be a file, directory, or Git blob as described above.
* `ganzua diff [<path>]` compares `INDEX:<path> <path>`
* `ganzua diff --git=<old> [<path>]` compares `<old>:<path> <path>`
* `ganzua diff --git=<old>...<new> [<path>]` compares `<old>:<path> <new>:<path>`

If the `<path>` is absent, the lockfile path is located in the current directory,
as if `.` had been passed.
If an explicit `--git` option is passed, the positional argument must be a path,
not a git blob.

**Options:**

* `--filter LOCKFILE-FILTER`
  Include/exclude packages. [default: use all]
* `--format [json|markdown]`
  Choose the output format, e.g. Markdown. [default: json]
* `--git COMMIT`
  Git commit to use for the diff. [default: INDEX]

  May be a single `<old>` revision, or a `<old>...<new>` range.
  In addition to `gitrevision` syntax, may use `INDEX` to name staged files.
* `--no-git`
  Disable Git functionality. [default: enabled]
* `--[no-]pypi-metadata`
  Look up PyPI metadata for locked packages. [default: off]

  This will add warnings for yanked or vulnerable packages.
* `--help`
  Show this help message and exit.

*Changed in Ganzua 0.5.0:* renamed `--name` to `--filter`.

<!-- command output end -->


## Output format <a name="examples"></a>

The `ganzua diff` command shows the package changes as JSON by default:

<details><summary><code>$ ganzua diff corpus/old-uv-project corpus/new-uv-project</code></summary>

```json
{
  "stat": {
    "total": 2,
    "added": 1,
    "removed": 0,
    "updated": 1
  },
  "packages": [
    {
      "name": "annotated-types",
      "old": null,
      "new": {
        "name": "annotated-types",
        "version": "0.7.0",
        "source": "pypi"
      }
    },
    {
      "name": "typing-extensions",
      "old": {
        "name": "typing-extensions",
        "version": "3.10.0.2",
        "source": "pypi"
      },
      "new": {
        "name": "typing-extensions",
        "version": "4.14.1",
        "source": "pypi"
      },
      "is_major_change": true
    }
  ]
}
```

</details>

We can opt in to the Markdown format for the diff, which will show a table:

<details><summary><code>$ ganzua diff corpus/old-uv-project corpus/new-uv-project --format=markdown</code></summary>

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

<details><summary><code>$ ganzua diff corpus/new-uv-project corpus/old-uv-project --format=markdown</code></summary>

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

Test cases for demonstrating how the `(M)`/`is_major_change` note works:

<!-- doctest: check ganzua diff notes -->

| package                     | old   | new     | notes |
|-----------------------------|-------|---------|-------|
| epoch-changed               | 1.2.3 | 1!1.2.3 | (M)   |
| epoch-zero                  | 1.2.3 | 0!1.2.3 |       |
| existence-added             | -     | 1.2.3   |       |
| existence-removed           | 1.2.3 | -       |       |
| major                       | 1.2.3 | 2.1.0   | (M)   |
| minor                       | 1.2.3 | 1.3.4   |       |
| validity-invalid-to-invalid | foo   | bar     | (M)   |
| validity-invalid-to-valid   | foo   | 1.2.3   | (M)   |
| validity-valid-to-invalid   | 1.2.3 | foo     | (M)   |
| zerover-change              | 0.1.2 | 0.2.0   | (M)   |
| zerover-same                | 0.1.2 | 0.1.3   |       |

Test cases for demonstrating how the `(D)`/`is_downgrade` note works:

<!-- doctest: check ganzua diff notes -->

| package   | old   | new   | notes |
|-----------|-------|-------|-------|
| downgrade | 1.3.4 | 1.0.1 | (D)   |
| upgrade   | 1.0.1 | 1.3.4 |       |

The Markdown diff can show notices when the source of a package changes.
When multiple entries have the same note, their IDs are deduplicated:

<details><summary><code>$ ganzua diff corpus/sources-poetry corpus/sources-uv --format=markdown</code></summary>

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

When a there are no changes, only the summary is shown.
The Markdown output omits the table:

<details><summary><code>$ ganzua diff corpus/new-uv-project corpus/new-uv-project</code></summary>

```json
{
  "stat": {
    "total": 0,
    "added": 0,
    "removed": 0,
    "updated": 0
  },
  "packages": []
}
```

</details>

<details><summary><code>$ ganzua diff corpus/new-uv-project corpus/new-uv-project --format=markdown</code></summary>

```
0 changed packages
```

</details>

## Diff arguments

A `ganzua diff` is always computed between two lockfiles or two versions of a lockfile.
This section describes the case that we want to compare two lockfiles in different locations.
The next section then discusses [Git support](#git-support).

The input paths may point to directories or lockfiles.
The following invocations are all equivalent:

<!-- doctest: compare output -->

* `$ ganzua diff corpus/old-uv-project         corpus/new-uv-project`
* `$ ganzua diff corpus/old-uv-project         corpus/new-uv-project/uv.lock`
* `$ ganzua diff corpus/old-uv-project/uv.lock corpus/new-uv-project`
* `$ ganzua diff corpus/old-uv-project/uv.lock corpus/new-uv-project/uv.lock`

<details><summary>output for the above commands</summary>

```json
{
  "stat": {
    "total": 2,
    "added": 1,
    "removed": 0,
    "updated": 1
  },
  "packages": [
    {
      "name": "annotated-types",
      "old": null,
      "new": {
        "name": "annotated-types",
        "version": "0.7.0",
        "source": "pypi"
      }
    },
    {
      "name": "typing-extensions",
      "old": {
        "name": "typing-extensions",
        "version": "3.10.0.2",
        "source": "pypi"
      },
      "new": {
        "name": "typing-extensions",
        "version": "4.14.1",
        "source": "pypi"
      },
      "is_major_change": true
    }
  ]
}
```

</details>

## Git support

<!-- doctest: clean example -->

A `ganzua diff` can compare lockfiles across Git versions.
For further details, see [Git](../git.md).

Note that there are two distinct invocation styles:

* 2 arguments: may be paths or git blob names of the form `<revision>:<path>`.
* 0 or 1 arguments: the argument must be a path (defaults to `.`), but we may use the `--git` argument to define Git versions.

<details><summary>setting up an example Git repo</summary>

```console
$ git -C $EXAMPLE init .
Initialized empty Git repository in ${EXAMPLE}/.git/
```

Adding an initial lockfile and committing:

<!-- doctest: create uv lockfile $EXAMPLE/uv.lock -->

| name    | version |
|---------|---------|
| initial | 1.2.3   |

```console
$ git -C $EXAMPLE add uv.lock
$ git -C $EXAMPLE commit -m 'initial commit'
[main (root-commit) 0803229] initial commit
 1 file changed, 8 insertions(+)
 create mode 100644 uv.lock
```

Editing the lockfile and committing:

<!-- doctest: create uv lockfile $EXAMPLE/uv.lock -->

| name    | version |
|---------|---------|
| initial | 1.2.3   |
| head    | 2.3.4   |

```console
$ git -C $EXAMPLE add uv.lock
$ git -C $EXAMPLE commit -m 'creating the HEAD commit'
[main 6185494] creating the HEAD commit
 1 file changed, 5 insertions(+)
```

Editing the lockfile and staging (adding to the index) – but not committing:

<!-- doctest: create uv lockfile $EXAMPLE/uv.lock -->

| name    | version |
|---------|---------|
| initial | 1.2.3   |
| head    | 2.3.4   |
| staged  | 3.4.5   |

```console
$ git -C $EXAMPLE add uv.lock
```

Editing the lockfile yet again, without staging:

<!-- doctest: create uv lockfile $EXAMPLE/uv.lock -->

| name    | version |
|---------|---------|
| initial | 1.2.3   |
| head    | 2.3.4   |
| staged  | 3.4.5   |
| dirty   | 0.0.0   |

</details>

By default, a `ganzua diff` will compare the worktree to the index, just like `git diff`.
All of these invocations are equivalent:

<!-- doctest: compare output -->

* `$ env -C $EXAMPLE ganzua diff`
* `$ env -C $EXAMPLE ganzua diff .`
* `$ env -C $EXAMPLE ganzua diff uv.lock`
* `$ env -C $EXAMPLE ganzua diff INDEX:uv.lock .`
* `$ env -C $EXAMPLE ganzua diff INDEX:uv.lock uv.lock`
* `$ env -C $EXAMPLE ganzua diff --git=INDEX`
* `$ env -C $EXAMPLE ganzua diff --git=INDEX .`

<details><summary>output for the above commands</summary>

```json
{
  "stat": {
    "total": 1,
    "added": 1,
    "removed": 0,
    "updated": 0
  },
  "packages": [
    {
      "name": "dirty",
      "old": null,
      "new": {
        "name": "dirty",
        "version": "0.0.0",
        "source": "pypi"
      }
    }
  ]
}
```

</details>

We can also compare the working tree to the HEAD commit (`@`),
for example with any of the following commands:

<!-- doctest: compare output -->
* `$ env -C $EXAMPLE ganzua diff HEAD:uv.lock .`
* `$ env -C $EXAMPLE ganzua diff HEAD:uv.lock uv.lock`
* `$ env -C $EXAMPLE ganzua diff --git=HEAD`
* `$ env -C $EXAMPLE ganzua diff --git=HEAD uv.lock`
* `$ env -C $EXAMPLE ganzua diff @:uv.lock .`
* `$ env -C $EXAMPLE ganzua diff --git=@`

<details><summary>output for the above commands</summary>

```json
{
  "stat": {
    "total": 2,
    "added": 2,
    "removed": 0,
    "updated": 0
  },
  "packages": [
    {
      "name": "dirty",
      "old": null,
      "new": {
        "name": "dirty",
        "version": "0.0.0",
        "source": "pypi"
      }
    },
    {
      "name": "staged",
      "old": null,
      "new": {
        "name": "staged",
        "version": "3.4.5",
        "source": "pypi"
      }
    }
  ]
}
```

</details>

We can compare two Git commits, which we'll name `HEAD^` and `HEAD` here.
In a `...` range, an empty side is interpreted as `HEAD`.

<!-- doctest: compare output -->
* `$ env -C $EXAMPLE ganzua diff HEAD^:uv.lock HEAD:uv.lock`
* `$ env -C $EXAMPLE ganzua diff --git=HEAD^...HEAD`
* `$ env -C $EXAMPLE ganzua diff --git=HEAD^...`
* `$ env -C $EXAMPLE ganzua diff --git=HEAD^... uv.lock`

<details><summary>output for the above commands</summary>

```json
{
  "stat": {
    "total": 1,
    "added": 1,
    "removed": 0,
    "updated": 0
  },
  "packages": [
    {
      "name": "head",
      "old": null,
      "new": {
        "name": "head",
        "version": "2.3.4",
        "source": "pypi"
      }
    }
  ]
}
```

</details>

Finally, we can compare commits to the staged files (index).
Any of these are equivalent:

<!-- doctest: compare output -->
* `$ env -C $EXAMPLE ganzua diff HEAD^:uv.lock INDEX:uv.lock`
* `$ env -C $EXAMPLE ganzua diff --git=HEAD^...INDEX`

<details><summary>output for the above commands</summary>

```json
{
  "stat": {
    "total": 2,
    "added": 2,
    "removed": 0,
    "updated": 0
  },
  "packages": [
    {
      "name": "head",
      "old": null,
      "new": {
        "name": "head",
        "version": "2.3.4",
        "source": "pypi"
      }
    },
    {
      "name": "staged",
      "old": null,
      "new": {
        "name": "staged",
        "version": "3.4.5",
        "source": "pypi"
      }
    }
  ]
}
```

</details>

Examples of some errors:

<details><summary>The two diff modes cannot be mixed.</summary>

```console
$ env -C $EXAMPLE ganzua diff --git=HEAD uv.lock uv.lock
Usage: ganzua diff [OPTIONS] [OLD] [NEW]
Try 'ganzua diff --help' for help.

Error: Cannot use `--git` if both OLD and NEW were given
[command exited with status 2]
```

```console
$ env -C $EXAMPLE ganzua diff --git=HEAD INDEX:uv.lock
Usage: ganzua diff [OPTIONS] [OLD] [NEW]
Try 'ganzua diff --help' for help.

Error: Could not read file from Git history: `HEAD:INDEX:uv.lock`
Note: Command `git cat-file blob HEAD:INDEX:uv.lock` exited with status 128
[command exited with status 2]
```

```console
$ env -C $EXAMPLE ganzua diff --git=INDEX HEAD:uv.lock
Usage: ganzua diff [OPTIONS] [OLD] [NEW]
Try 'ganzua diff --help' for help.

Error: Could not read file from Git history: `:HEAD:uv.lock`
Note: Command `git cat-file blob :HEAD:uv.lock` exited with status 128
[command exited with status 2]
```

```console
$ env -C $EXAMPLE ganzua diff HEAD:uv.lock
Usage: ganzua diff [OPTIONS] [OLD] [NEW]
Try 'ganzua diff --help' for help.

Error: Could not read file from Git history: `:HEAD:uv.lock`
Note: Command `git cat-file blob :HEAD:uv.lock` exited with status 128
[command exited with status 2]
```

```console
$ env -C $EXAMPLE ganzua diff --git=HEAD uv.lock INDEX:uv.lock
Usage: ganzua diff [OPTIONS] [OLD] [NEW]
Try 'ganzua diff --help' for help.

Error: Cannot use `--git` if both OLD and NEW were given
[command exited with status 2]
```

</details>


<details><summary>Git mode can be disabled explicitly.</summary>

Under the `--no-git` mode, arguments are interpreted as ordinary paths.

```console
$ env -C $EXAMPLE ganzua diff --no-git HEAD:uv.lock uv.lock
Usage: ganzua diff [OPTIONS] [OLD] [NEW]
Try 'ganzua diff --help' for help.

Error: OLD: File `HEAD:uv.lock` does not exist.
[command exited with status 2]
```

Under the `--no-git` mode, explicitly using the `--git` option causes an error.

```console
$ env -C $EXAMPLE ganzua diff --no-git --git=HEAD
Usage: ganzua diff [OPTIONS] [OLD] [NEW]
Try 'ganzua diff --help' for help.

Error: OLD: Cannot read `HEAD:uv.lock` because Git support was disabled.
[command exited with status 2]
```

</details>

## Filters

Can filter the packages to be diffed by name.
For more details, see the [filter manual](../filters.md).
Filtering was added in Ganzua 0.4.0.

<details><summary><code>$ ganzua diff $CORPUS/old-uv-project $CORPUS/new-uv-project --filter='typing*' --format=markdown</code></summary>

```
1 changed packages (1 updated)

| package           | old      | new    | notes |
|-------------------|----------|--------|-------|
| typing-extensions | 3.10.0.2 | 4.14.1 | (M)   |

* (M) major change
```

</details>

<details><summary><code>$ ganzua diff $CORPUS/old-uv-project $CORPUS/new-uv-project --filter='nonexistent' --format=markdown</code></summary>

```
0 changed packages
```

</details>

## PyPI metadata

Using the `--pypi-metadata` flag will load package metadata from PyPI,
which can be used to audit for known-vulnerable or yanked packages,
and will also show project URLs in the JSON output.
See the [PyPI metadata](../pypi-metadata.md) feature reference for examples and further details.

## Other examples

Hidden features:

<details><summary>Unstable: there's a hidden <code>--md-links</code> option.</summary>

```console
$ ganzua diff $CORPUS/old-uv-project $CORPUS/new-uv-project --format=markdown --md-links
2 changed packages (1 added, 1 updated)

| package                                                   | old      | new    | notes |
|-----------------------------------------------------------|----------|--------|-------|
| [annotated-types](https://pypi.org/p/annotated-types)     | -        | 0.7.0  |       |
| [typing-extensions](https://pypi.org/p/typing-extensions) | 3.10.0.2 | 4.14.1 | (M)   |

* (M) major change
```

</details>


## JSON Schema

Download: [schema.diff.json](schema.diff.json)

<!-- command output: ganzua schema diff --format=markdown -->

**Properties:**

* **`stat`**: [DiffStat](#type.DiffStat)
* **`packages`**: array([DiffEntry](#type.DiffEntry))

### type `DiffStat` {#type.DiffStat}

**Properties:**

* **`total`**: int
* **`added`**: int
* **`removed`**: int
* **`updated`**: int

### type `DiffEntry` {#type.DiffEntry}

**Properties:**

* **`name`**: string\
  Name of the package being diffed.

  *Added in Ganzua 0.4.0:* previously, the package name was implicit.
* **`old`**: [LockedPackageNoMeta](#type.LockedPackageNoMeta) | null
* **`new`**: [LockedPackageNoMeta](#type.LockedPackageNoMeta) | null
* **`pypi_metadata`**?: [PyPIMetadata](#type.PyPIMetadata)\
  PyPI metadata for the `new` version, if any.

  This field will only be populated if
  metadata was explicitly requested via `--pypi-metadata`,
  the package seems to have been installed from PyPI,
  and PyPI successfully provided metadata for the new version.

  *Added in Ganzua 0.5.0*.
* **`is_major_change`**?: bool\
  True if there was a major version change.

  This doesn't literally mean "the SemVer-major version component changed",
  but is intended to highlight version changes that are likely to have breakage.
* **`is_downgrade`**?: bool\
  True if the version was downgraded.
* **`is_source_change`**?: bool\
  True if the package source changed.
* **`is_yanked`**?: bool\
  True if the new version was yanked (per `pypi_metadata`).

  *Added in Ganzua 0.5.0*.
* **`is_vulnerable`**?: bool\
  True if the new version has a known vulnerability (per `pypi_metadata`).

  For the purposes of this flag, withdrawn vulnerabilities are ignored.

  *Added in Ganzua 0.5.0*.

### type `LockedPackageNoMeta` {#type.LockedPackageNoMeta}

**Properties:**

* **`name`**: string\
  Name of the package.

  *Added in Ganzua 0.4.0:* previously, the package name was implicit.
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

### type `PyPIMetadata` {#type.PyPIMetadata}

Extra PyPI metadata that relates to a specific package version.

*Added in Ganzua 0.5.0*.

**Properties:**

* **`yanked`**?: string\
  If this package version was yanked, the reason given.

  If no reason was given, a yanked package will use an empty string here.
* **`vulnerabilities`**?: array([Vulnerability](#type.Vulnerability))\
  If this package version has vulnerabilities, details on those.
* **`project_urls`**?: mapping(string → string)\
  The project URLs declared in the package metadata (label → url).

  Well-known labels will have been replaced by their canonical name,
  e.g. `What's New?` will be replaced by `changelog`.

  Specifications:
  * <https://packaging.python.org/en/latest/specifications/core-metadata/#project-url-multiple-use>
  * <https://packaging.python.org/en/latest/specifications/well-known-project-urls/#well-known-project-urls>

### type `Vulnerability` {#type.Vulnerability}

Information about a known vulnerability for a specific package version.

Matches the [PyPI JSON API](https://docs.pypi.org/api/json/#known-vulnerabilities) exactly,
which in turn is based on the [Open Source Vulnerability format](https://ossf.github.io/osv-schema/).

**Properties:**

* **`id`**: string
* **`source`**: string
* **`link`**?: string | null
* **`aliases`**?: array(string) | null
* **`details`**?: string | null
* **`summary`**?: string | null
* **`fixed_in`**?: array(string) | null
* **`withdrawn`**?: string | null

<!-- command output end -->
