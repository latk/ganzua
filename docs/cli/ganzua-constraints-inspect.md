# ganzua constraints inspect

<!-- command output: ganzua help constraints inspect --markdown --markdown-links={slug}.md -->

Usage: `ganzua constraints inspect [OPTIONS] [PYPROJECT]`

List all constraints in the `pyproject.toml` file.

The `PYPROJECT` argument should point to a `pyproject.toml` file,
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

Can inspect the constraints of a `pyproject.toml` file as JSON or Markdown:

<details><summary><code>$ ganzua constraints inspect corpus/new-uv-project</code></summary>

```json
{
  "requirements": [
    {
      "name": "annotated-types",
      "specifier": ">=0.7.0"
    },
    {
      "name": "typing-extensions",
      "specifier": ">=4"
    }
  ]
}
```

</details>

<details><summary><code>$ ganzua constraints inspect corpus/new-uv-project --format=markdown</code></summary>

```
| package           | version |
|-------------------|---------|
| annotated-types   | >=0.7.0 |
| typing-extensions | >=4     |
```

</details>

The same package can appear in multiple constraints, in particular:

* in different extras: `[package.optional-dependencies]`, `[tool.poetry.extras]`
* in different groups: `[dependency-groups]`, `[tool.poetry.group.*.dependencies]`

Due to inheritance mechanisms like `{include-group = "…"}`, the same constraint can appear in multiple extras (Poetry only) and multiple groups (all flavors).

Here are some examples of how the Ganzua output looks in these cases:

<details><summary><code>$ ganzua constraints inspect corpus/poetry-multiple-groups</code></summary>

```json
{
  "requirements": [
    {
      "name": "annotated-types",
      "specifier": ">=0.7.0"
    },
    {
      "name": "annotated-types",
      "specifier": "<0.8.0",
      "in_groups": [
        "dev",
        "types"
      ]
    },
    {
      "name": "typing-extensions",
      "specifier": "<5.0.0,>=4.15.0",
      "in_groups": [
        "types"
      ]
    },
    {
      "name": "typing-extensions",
      "specifier": "^4.15",
      "in_extras": [
        "dev",
        "types"
      ]
    }
  ]
}
```

</details>

<details><summary><code>$ ganzua constraints inspect corpus/poetry-multiple-groups --format=markdown</code></summary>

```
| package           | version         | group/extra                |
|-------------------|-----------------|----------------------------|
| annotated-types   | <0.8.0          | group `dev`, group `types` |
| annotated-types   | >=0.7.0         |                            |
| typing-extensions | <5.0.0,>=4.15.0 | group `types`              |
| typing-extensions | ^4.15           | extra `dev`, extra `types` |
```

</details>


## JSON Schema

Download: [schema.constraints-inspect.json](schema.constraints-inspect.json)

<!-- command output: ganzua schema constraints-inspect --format=markdown -->

**Properties:**

* **`requirements`**: array([Requirement](#type.Requirement))

### type `Requirement` {#type.Requirement}

A resolver-agnostic Requirement model.

This corresponds to one dependency entry in a `pyproject.toml` file.
This is a lexical/textual concept about information in the file,
intended for inspection and edits.

Requirements can be difficult to interpret.
There might be multiple Requirements that point to the same package,
potentially with complementary or contradictory contents.
Features like `[dependency-groups]` or `[tool.poetry.extras]`
can include the same Requirement in multiple places,
which is why the `in_groups` and `in_extras` fields may have multiple values.

**Properties:**

* **`name`**: string\
  The name of the required package.
* **`specifier`**: string\
  Version specifier for the required package, may use PEP-508 or Poetry syntax.
* **`extras`**?: array(string)\
  Extras enabled for the required package.
* **`marker`**?: string\
  Environment marker expression describing when this requirement should be installed.
* **`in_groups`**?: array(string)\
  Dependency groups that this requirement is part of.
* **`in_extras`**?: array(string)\
  Extras that this optional requirement is part of.

  Requirements can only be part of one extra (with some exceptions).

  The `groups` and `in_extras` fields are effectively mutually exclusive.

  Special cases for legacy Poetry:

  * When using `[tool.poetry.extras]`, one requirement can be part of multiple extras.
  * The `marker` might also reference extras.

<!-- command output end -->
