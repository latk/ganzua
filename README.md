Ganzua
======

A tool for extracting dependency information from Python lockfiles.

For example, we can summarize the differences between two `uv.lock` files:

```console
$ ganzua diff tests/{old,new}-uv-project/uv.lock
{
  "annotated-types": {
    "old": null,
    "new": "0.7.0"
  },
  "typing-extensions": {
    "old": "3.10.0.2",
    "new": "4.14.1"
  }
}
```

## Usage

<!-- begin usage -->

Usage: `ganzua [OPTIONS] COMMAND [ARGS]...`

Inspect Python dependency lockfiles (uv and Poetry).

**Options:**

* `--help`
  Show this help message and exit.

**Commands:**

* `help`
  Show help for the application or a specific subcommand.
* `inspect`
  Inspect a lockfile.
* `diff`
  Compare two lockfiles.
* `update-constraints`
  Update pyproject.toml dependency constraints to match the lockfile.
* `remove-constraints`
  Remove any dependency version constraints from the `pyproject.toml`.
* `schema`
  Show the JSON schema for the output of the given command.

Ganzua is licensed under the Apache-2.0 license.


### ganzua help

Usage: `ganzua help [OPTIONS] [SUBCOMMAND]...`

Show help for the application or a specific subcommand.

**Options:**

* `--all`
  Also show help for all subcommands.
* `--markdown`
  Output help in Markdown format.


### ganzua inspect

Usage: `ganzua inspect [OPTIONS] LOCKFILE`

Inspect a lockfile.

**Options:**

* `--format [json|markdown]`
  Choose the output format, e.g. Markdown. [default: json]
* `--help`
  Show this help message and exit.


### ganzua diff

Usage: `ganzua diff [OPTIONS] OLD NEW`

Compare two lockfiles.

**Options:**

* `--format [json|markdown]`
  Choose the output format, e.g. Markdown. [default: json]
* `--help`
  Show this help message and exit.


### ganzua update-constraints

Usage: `ganzua update-constraints [OPTIONS] LOCKFILE PYPROJECT`

Update pyproject.toml dependency constraints to match the lockfile.

Of course, the lockfile should always be a valid solution for the constraints.
But this tool will increment the constraints to match the current locked versions.
Often, constraints are somewhat relaxed.
This tool will try to be as granular as the original constraint.
For example, given the old constraint `foo>=3.5` and the new version `4.7.2`,
the constraint would be updated to `foo>=4.7`.

**Options:**

* `--backup PATH`
  Store a backup in this file.
* `--help`
  Show this help message and exit.


### ganzua remove-constraints

Usage: `ganzua remove-constraints [OPTIONS] PYPROJECT`

Remove any dependency version constraints from the `pyproject.toml`.

This can be useful for allowing uv/Poetry to update to the most recent versions,
ignoring the previous constraints. Approximate recipe:

```bash
ganzua remove-constraints --backup=pyproject.toml.bak pyproject.toml
uv lock --upgrade  # perform the upgrade
mv pyproject.toml.bak pyproject.toml  # restore old constraints
ganzua update-constraints uv.lock pyproject.toml
uv lock
```

**Options:**

* `--backup PATH`
  Store a backup in this file.
* `--help`
  Show this help message and exit.


### ganzua schema

Usage: `ganzua schema [OPTIONS] {inspect|diff}`

Show the JSON schema for the output of the given command.

**Options:**

* `--help`
  Show this help message and exit.

<!-- end usage -->

##  What does Ganzua mean?

The Spanish term *ganzúa* means lockpick. It is pronounced *gan-THU-a*.

This `ganzua` tool for interacting with Python dependency lockfiles
is unrelated to the [2004 cryptoanalysis tool of the same name](https://ganzua.sourceforge.net/en/index.html).

## License

Copyright 2025 Lukas Atkinson

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
