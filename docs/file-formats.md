# File formats

This document describes file formats supported by Ganzua.

## `pyproject.toml` {#pyproject.toml}

Ganzua will only load constraints from `pyproject.toml` files.
Supported sections:

* `[project.dependencies]` and `[project.optional-dependencies]`
  * specification: <https://packaging.python.org/en/latest/specifications/pyproject-toml/>
  * [PEP 621 – Storing project metadata in pyproject.toml](https://peps.python.org/pep-0621/)
* `[dependency-groups]` table
  * specification: <https://packaging.python.org/en/latest/specifications/dependency-groups/>
  * [PEP 735 – Dependency Groups in pyproject.toml](https://peps.python.org/pep-0735/)
* `[tool.poetry.dependencies]` and `[tool.poetry.group.*.dependencies]`

Example with normal dependencies, optional dependencies, and dependency groups:

<details><summary><code>$ ganzua constraints inspect $CORPUS/constraints-uv-pyproject.toml --format=markdown</code></summary>

```
| package           | version         | group/extra                      |
|-------------------|-----------------|----------------------------------|
| annotated-types   | ==0.6.*,>=0.6.1 | extra `extra1`                   |
| annotated-types   | ~=0.6.1         | group `group-b`                  |
| merrily-ignored   |                 |                                  |
| ndr               |                 | extra `extra3`                   |
| typing-extensions | <4,>=3          |                                  |
| typing-extensions | ~=3.4           | group `group-a`, group `group-b` |
```

</details>

## Lockfiles

<!-- doctest: json schema to validate ganzua._lockfile:AnyLockfile -->

Support both uv and Poetry lockfile formats.

The names of the files are ignored.
Instead, the supported format is sniffed from the contents of each lockfile.

**Variants:**

* [UvLockfileV1](#type.UvLockfileV1)
* [PoetryLockfileV2](#type.PoetryLockfileV2)

### type `UvLockfileV1` {#type.UvLockfileV1}

The uv lockfile format (v1).

Documentation: <https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile>

There is no specification for this schema by uv/Astral.
However, uv promises [some compatibility guarantees](https://docs.astral.sh/uv/concepts/resolution/#lockfile-versioning).
Therefore, we pin this model to only match the v1.x schema.
Future changes will get their own model.

**Properties:**

* **`version`**: `1`
* **`package`**: array([UvLockfileV1Package](#type.UvLockfileV1Package))

### type `UvLockfileV1Package` {#type.UvLockfileV1Package}

Package information as locked by uv.

Ganzua ignores details such as hashes or wheels.

**Properties:**

* **`name`**: string\
  The name of the package.
* **`version`**?: string\
  The locked version of the package.
  Note that some packages don't have a version.
* **`source`**: [UvLockfileV1Source](#type.UvLockfileV1Source)\
  Where this package was obtained from.
  Uv provides this information for *every* package.

### type `UvLockfileV1Source` {#type.UvLockfileV1Source}

Package source information as locked by uv.

Only ONE field may be set (or `url` + `subdirectory`).

The lockfile sources do not match the [`[tool.uv.sources]` syntax](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-sources).
Instead, the possible sources are defined in the [uv-resolver `SourceWire` enum](https://github.com/astral-sh/uv/blob/141369ce73b7b0b4e005b0f45107d13c828a99e0/crates/uv-resolver/src/lock/mod.rs#L3736).

**Properties:**

* **`registry`**?: string\
  URL or path pointing to an index.
* **`git`**?: string
* **`url`**?: string
* **`subdirectory`**?: string
* **`path`**?: string
* **`directory`**?: string
* **`editable`**?: string
* **`virtual`**?: string

### type `PoetryLockfileV2` {#type.PoetryLockfileV2}

The Poetry lockfile format (v2).

There is no official documentation for this lockfile format.
The [`Locker` class](https://github.com/python-poetry/poetry/blob/1c059eadbb4c2bf29e01a61979b7f50263c9e506/src/poetry/packages/locker.py#L53) comes close.

**Properties:**

* **`metadata`**: object\
  Metadata block for the lockfile.
  Ganzua doesn't actively use this information, other than to distinguish lockfile formats from each other.

  **Properties:**

  * **`lock-version`**: string\
    Version of the Poetry lockfile format.

    At the time of writing, the lockfile format version is at `2.1`.
    Ganzua doesn't validate this, and accepts any string for now.
  * **`content-hash`**: string\
    Poetry hashes a canonical version of all requirements and stores it in the lockfile.

    Ganzua requires the presence of this field, but does not validate the contents in any way.
* **`package`**: array([PoetryLockfileV2Package](#type.PoetryLockfileV2Package))

### type `PoetryLockfileV2Package` {#type.PoetryLockfileV2Package}

Package information as locked by Poetry.

**Properties:**

* **`name`**: string
* **`version`**: string
* **`source`**?: [PoetryLockfileV2Source](#type.PoetryLockfileV2Source)

### type `PoetryLockfileV2Source` {#type.PoetryLockfileV2Source}

**Properties:**

* **`type`**?: string\
  One of `directory`, `file`, `url`, `git`, `hg`, `legacy`, `pypi`.
  The `pypi` name is not case sensitive.
* **`url`**?: string
* **`reference`**?: string
* **`resolved_reference`**?: string
* **`subdirectory`**?: string

<!-- doctest: json schema end -->
