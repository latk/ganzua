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
  "packages": {
    "example": {
      "version": "0.1.0",
      "source": {
        "direct": "."
      }
    },
    "typing-extensions": {
      "version": "3.10.0.2",
      "source": "pypi"
    }
  }
}
```

</details>

<details><summary><code>$ ganzua inspect corpus/new-uv-project</code></summary>

```json
{
  "packages": {
    "annotated-types": {
      "version": "0.7.0",
      "source": "pypi"
    },
    "example": {
      "version": "0.1.0",
      "source": {
        "direct": "."
      }
    },
    "typing-extensions": {
      "version": "4.14.1",
      "source": "pypi"
    }
  }
}
```

</details>

<details><summary><code>$ ganzua inspect corpus/old-poetry-project</code></summary>

```json
{
  "packages": {
    "typing-extensions": {
      "version": "3.10.0.2",
      "source": "default"
    }
  }
}
```

</details>

<details><summary><code>$ ganzua inspect corpus/new-poetry-project</code></summary>

```json
{
  "packages": {
    "annotated-types": {
      "version": "0.7.0",
      "source": "default"
    },
    "typing-extensions": {
      "version": "4.14.1",
      "source": "default"
    }
  }
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
  "packages": {
    "annotated-types": {
      "version": "0.7.0",
      "source": "pypi"
    },
    "example": {
      "version": "0.1.0",
      "source": {
        "direct": "."
      }
    },
    "typing-extensions": {
      "version": "4.14.1",
      "source": "pypi"
    }
  }
}
```

</details>

It is possible for a locked package to have no version
(see [issue #4](https://github.com/latk/ganzua/issues/4)).
In this case, Ganzua will use the pseudo-version `0+undefined`:

<details><summary><code>$ ganzua inspect corpus/setuptools-dynamic-version</code></summary>

```json
{
  "packages": {
    "setuptools-dynamic-version": {
      "version": "0+undefined",
      "source": {
        "direct": "."
      }
    }
  }
}
```

</details>

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
