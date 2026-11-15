# ganzua inspect

<!-- command output: ganzua help inspect --markdown --markdown-links={slug}.md -->

Usage: `ganzua inspect [OPTIONS] [LOCKFILE]`

Inspect a lockfile.

The `LOCKFILE` argument can be any of the following:

* file: use that path as the lockfile (e.g. `uv.lock` or `poetry.lock`)
* directory: look for a lockfile in that directory
* gitrevision: a `<commit>:<path>` identifying a lockfile in the Git history

If this argument is not specified,
the one in the current working directory will be used.

**Options:**

* `--filter LOCKFILE-FILTER`
  Include/exclude packages. [default: use all]
* `--format [json|markdown]`
  Choose the output format, e.g. Markdown. [default: json]
* `--no-git`
  Disable Git functionality. [default: enabled]
* `--[no-]pypi-metadata`
  Look up PyPI metadata for locked packages. [default: off]

  This will add warnings for yanked or vulnerable packages.
* `--help`
  Show this help message and exit.

*Changed in Ganzua 0.5.0:* renamed `--name` to `--filter`.

<!-- command output end -->

## Examples

We can load various example lockfiles:

<details><summary><code>$ ganzua inspect corpus/old-uv-project</code></summary>

```json
{
  "packages": [
    {
      "name": "example",
      "version": "0.1.0",
      "source": {
        "direct": "."
      }
    },
    {
      "name": "typing-extensions",
      "version": "3.10.0.2",
      "source": "pypi"
    }
  ]
}
```

</details>

<details><summary><code>$ ganzua inspect corpus/new-uv-project</code></summary>

```json
{
  "packages": [
    {
      "name": "annotated-types",
      "version": "0.7.0",
      "source": "pypi"
    },
    {
      "name": "example",
      "version": "0.1.0",
      "source": {
        "direct": "."
      }
    },
    {
      "name": "typing-extensions",
      "version": "4.14.1",
      "source": "pypi"
    }
  ]
}
```

</details>

<details><summary><code>$ ganzua inspect corpus/old-poetry-project</code></summary>

```json
{
  "packages": [
    {
      "name": "typing-extensions",
      "version": "3.10.0.2",
      "source": "default"
    }
  ]
}
```

</details>

<details><summary><code>$ ganzua inspect corpus/new-poetry-project</code></summary>

```json
{
  "packages": [
    {
      "name": "annotated-types",
      "version": "0.7.0",
      "source": "default"
    },
    {
      "name": "typing-extensions",
      "version": "4.14.1",
      "source": "default"
    }
  ]
}
```

</details>

<details><summary><code>$ ganzua inspect corpus/new-uv-project/pylock.exported.toml</code></summary>

```json
{
  "packages": [
    {
      "name": "annotated-types",
      "version": "0.7.0",
      "source": "pypi"
    },
    {
      "name": "typing-extensions",
      "version": "4.14.1",
      "source": "pypi"
    }
  ]
}
```

</details>

Instead of producing JSON output, we can summarize lockfiles as Markdown:

```console
$ ganzua inspect corpus/old-uv-project --format=markdown
| package           | version  |
|-------------------|----------|
| example           | 0.1.0    |
| typing-extensions | 3.10.0.2 |
```

The input paths may point to directories or lockfiles.
The following invocations are all equivalent:

<!-- doctest: compare output -->

* `$ ganzua inspect corpus/new-uv-project`
* `$ ganzua inspect corpus/new-uv-project/uv.lock`

<details><summary>output for the above commands</summary>

```json
{
  "packages": [
    {
      "name": "annotated-types",
      "version": "0.7.0",
      "source": "pypi"
    },
    {
      "name": "example",
      "version": "0.1.0",
      "source": {
        "direct": "."
      }
    },
    {
      "name": "typing-extensions",
      "version": "4.14.1",
      "source": "pypi"
    }
  ]
}
```

</details>

It is possible for a locked package to have no version
(see [issue #4](https://github.com/latk/ganzua/issues/4)).
In this case, Ganzua will use the pseudo-version `0+undefined`:

<details><summary><code>$ ganzua inspect corpus/setuptools-dynamic-version</code></summary>

```json
{
  "packages": [
    {
      "name": "setuptools-dynamic-version",
      "version": "0+undefined",
      "source": {
        "direct": "."
      }
    }
  ]
}
```

</details>

Unknown file paths produce an error:

<details><summary><code>$ ganzua inspect $EXAMPLE/unknown</code></summary>

```
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: LOCKFILE: File `${EXAMPLE}/unknown` does not exist.
[command exited with status 2]
```

</details>

### Split versions

It is possible for a project to have multiple conflicting requirements, e.g. for different Python versions, extras, or groups:

<details><summary><code>$ cat $CORPUS/split/pyproject.toml</code></summary>

```toml
[project]
name = "split"
version = "0.1.0"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "typing_extensions >=4 ; python_version >= '3.14'",
  "typing_extensions >=3,<4 ; python_version < '3.14'",
]
```

</details>

When inspecting the lockfile, Ganzua will show all candidates:

<details><summary><code>$ ganzua inspect $CORPUS/split/uv.lock</code></summary>

```json
{
  "packages": [
    {
      "name": "split",
      "version": "0.1.0",
      "source": {
        "direct": "."
      }
    },
    {
      "name": "typing-extensions",
      "version": "3.10.0.2",
      "source": "pypi"
    },
    {
      "name": "typing-extensions",
      "version": "4.15.0",
      "source": "pypi"
    }
  ]
}
```

</details>

<details><summary><code>$ ganzua inspect $CORPUS/split/poetry.lock</code></summary>

```json
{
  "packages": [
    {
      "name": "typing-extensions",
      "version": "3.10.0.2",
      "source": "default"
    },
    {
      "name": "typing-extensions",
      "version": "4.15.0",
      "source": "default"
    }
  ]
}
```

</details>

Split version support was added in *Ganzua 0.4.0*.
For background on this, see the issue [ganzua#5](https://github.com/latk/ganzua/issues/5).

### Filtering

<!-- doctest: clean example -->

<!--
```console
$ cp corpus/new-uv-project/uv.lock $EXAMPLE/uv.lock
```
-->

Normally, inspecting a lockfile will show all results:

<details open><summary><code>$ ganzua inspect $EXAMPLE --format=markdown</code></summary>

```
| package           | version |
|-------------------|---------|
| annotated-types   | 0.7.0   |
| example           | 0.1.0   |
| typing-extensions | 4.14.1  |
```

</details>

However, we can use a `--filter` to only look at a specific package:

<details open><summary><code>$ ganzua inspect $EXAMPLE --filter=annotated-types --format=markdown</code></summary>

```
| package         | version |
|-----------------|---------|
| annotated-types | 0.7.0   |
```

</details>

Can also use glob patterns to select matching packages:

<details><summary><code>$ ganzua inspect $EXAMPLE --filter='*ex*' --format=markdown</code></summary>

```
| package           | version |
|-------------------|---------|
| example           | 0.1.0   |
| typing-extensions | 4.14.1  |
```

</details>

For further details on filters, see the [filter manual](../filters.md).

Filtering was added in *Ganzua 0.4.0*.

<details><summary>Unstable: there's a hidden <code>--md-links</code> option.</summary>

```console
$ ganzua inspect $EXAMPLE --format=markdown --md-links
| package                                                   | version |
|-----------------------------------------------------------|---------|
| [annotated-types](https://pypi.org/p/annotated-types)     | 0.7.0   |
| example                                                   | 0.1.0   |
| [typing-extensions](https://pypi.org/p/typing-extensions) | 4.14.1  |
```

</details>

### PyPI metadata

Using the `--pypi-metadata` flag will load package metadata from PyPI,
which can be used to audit for known-vulnerable or yanked packages,
and will also show project URLs in the JSON output.
See the [PyPI metadata](../pypi-metadata.md) feature reference for examples and further details.

## JSON Schema

Download: [schema.inspect.json](schema.inspect.json)

<!-- command output: ganzua schema inspect --format=markdown -->

**Properties:**

* **`packages`**: array([LockedPackage](#type.LockedPackage))\
  All packages in the lockfile.

  In case of split versions, there can be multiple entries with the same package name.

  *Changed in Ganzua 0.4.0:* `packages` is now a list.
  Previously, it was a `name → LockedPackage` table.

### type `LockedPackage` {#type.LockedPackage}

**Properties:**

* **`name`**: string\
  Name of the package.

  *Added in Ganzua 0.4.0:* previously, the package name was implicit.
* **`version`**: string
* **`source`**: `pypi` | `default` | `other` | [SourceRegistry](#type.SourceRegistry) | [SourceDirect](#type.SourceDirect)
* **`pypi_metadata`**?: [PyPIMetadata](#type.PyPIMetadata)\
  PyPI metadata for the locked package, if any.

  This field will only be populated if
  metadata was explicitly requested via `--pypi-metadata`,
  the package seems to have been installed from PyPI,
  and PyPI successfully provided metadata for the new version.

  *Added in Ganzua 0.5.0*.
* **`is_yanked`**?: bool\
  True if the locked package was yanked (per `pypi_metadata`).

  *Added in Ganzua 0.5.0*.
* **`is_vulnerable`**?: bool\
  True if the locked package has a known vulnerability (per `pypi_metadata`).

  For the purposes of this flag, withdrawn vulnerabilities are ignored.

  *Added in Ganzua 0.5.0*.

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
