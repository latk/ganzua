# ganzua inspect

<!-- command output: ganzua help inspect --markdown --markdown-links={slug}.md -->

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

For background on this, see the issue [ganzua#5](https://github.com/latk/ganzua/issues/5).


## JSON Schema

Download: [schema.inspect.json](schema.inspect.json)

<!-- command output: ganzua schema inspect --format=markdown -->

**Properties:**

* **`packages`**: array([LockedPackage](#type.LockedPackage))\
  All packages in the lockfile.

  In case of split versions, there can be multiple entries with the same package name.

  *Changed in Ganzua NEXT:* `packages` is now a list.
  Previously, it was a `name → LockedPackage` table.

### type `LockedPackage` {#type.LockedPackage}

**Properties:**

* **`name`**: string\
  Name of the package.

  *Added in Ganzua NEXT:* previously, the package name was implicit.
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
