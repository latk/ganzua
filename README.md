Ganzua
======

[ GitHub: [latk/ganzua](https://github.com/latk/ganzua)
| PyPI: [ganzua](https://pypi.org/project/ganzua/)
| Documentation: <https://ganzua.latk.de>
]

<!-- ANCHOR: motivating-example -->

Ganzua is  tool for picking dependency information from Python lockfiles,
and manipulating the version constraints in `pyproject.toml` files.

For example, we can summarize the differences between two `uv.lock` files.
Ganzua is designed for scripting, so by default we get JSON output:

```console
$ ganzua diff tests/{old,new}-uv-project/uv.lock
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

We can also opt in to Markdown (GFM) output, which will produce a summary and a table:

```console
$ ganzua diff --format=markdown tests/{old,new}-uv-project/uv.lock
2 changed packages (1 added, 1 updated)

| package           | old      | new    | notes |
|-------------------|----------|--------|-------|
| annotated-types   | -        | 0.7.0  |       |
| typing-extensions | 3.10.0.2 | 4.14.1 | (M)   |

* (M) major change
```

Aside from inspecting or diffing lockfiles,
we can extract and manipulate constraints from `pyproject.toml` files:

```console
$ ganzua constraints inspect --format=markdown tests/new-uv-project/pyproject.toml
| package           | version |
|-------------------|---------|
| annotated-types   | >=0.7.0 |
| typing-extensions | >=4     |
```

For more examples and further background, see the [announcement blog post](https://lukasatkinson.de/2025/ganzua/).

<!-- ANCHOR_END: motivating-example -->

## Installation

<!-- ANCHOR: installation -->

Ganzua is available on PyPI: <https://pypi.org/project/ganzua/>

Recommended: run or install via the [`uv` package manager](https://docs.astral.sh/uv/):

* `uvx ganzua` to try Ganzua without installation
* `uv tool install ganzua` to install Ganzua on your machine

Alternative: run or install via the [`pipx` tool](https://pipx.pypa.io/):

* `pipx run ganzua` to try Ganzua without installation
* `pipx install ganzua` to install Ganzua on your machine

When invoking Ganzua in scripts or in a CI job, consider pinning or constraining a version.
This prevents your scripts from breaking when Ganzua has an incompatible change.
For example:

* `uvx ganzua==0.3.0` to pin an exact version
* `uvx 'ganzua>=0.3.0,<0.4.0'` to constraint to a version range (remember quotes to escape special characters like `<`)

To preview a bleeding-edge version without waiting for a PyPI release, you can install directly from the Ganzua repository on GitHub. For example:

* `uvx git+https://github.com/latk/ganzua.git`
* `pipx run --spec git+https://github.com/latk/ganzua.git ganzua`

Do not add Ganzua as a dependency to your project, instead prefer invoking Ganzua via `uvx` or `pipx run`.
You can technically install Ganzua into an existing venv using tools like uv, Poetry, or Pip.
But since Ganzua might require conflicting dependencies, and might even need a different Python version, this is likely to cause more problems than it solves.

<!-- ANCHOR_END: installation -->

## Usage

Usage: `ganzua [OPTIONS] COMMAND [ARGS]...`

See the [command line reference](https://ganzua.latk.de/cli/) on the website
for detailed docs on each subcommand:

<!-- command output: ganzua help --markdown --subcommand-style=flat --subcommand-path --markdown-links='https://ganzua.latk.de/cli/{slug}.html' -->

* [`ganzua`](https://ganzua.latk.de/cli/ganzua.html)
  Inspect Python dependency lockfiles (uv and Poetry).
* [`ganzua help`](https://ganzua.latk.de/cli/ganzua-help.html)
  Show help for the application or a specific subcommand.
* [`ganzua inspect`](https://ganzua.latk.de/cli/ganzua-inspect.html)
  Inspect a lockfile.
* [`ganzua diff`](https://ganzua.latk.de/cli/ganzua-diff.html)
  Compare two lockfiles.
* [`ganzua constraints`](https://ganzua.latk.de/cli/ganzua-constraints.html)
  Work with `pyproject.toml` constraints.
* [`ganzua constraints inspect`](https://ganzua.latk.de/cli/ganzua-constraints-inspect.html)
  List all constraints in the `pyproject.toml` file.
* [`ganzua constraints bump`](https://ganzua.latk.de/cli/ganzua-constraints-bump.html)
  Update `pyproject.toml` dependency constraints to match the lockfile.
* [`ganzua constraints reset`](https://ganzua.latk.de/cli/ganzua-constraints-reset.html)
  Remove or relax any dependency version constraints from the `pyproject.toml`.
* [`ganzua schema`](https://ganzua.latk.de/cli/ganzua-schema.html)
  Show the JSON schema for the output of the given command.

<!-- command output end -->

## Support

<!-- ANCHOR: support -->

Ganzua is Open Source software, provided to you free of charge and on an "as is" basis.
You are not entitled to support, help, or bugfixes of any kind.

Nevertheless, the Ganzua project may occasionally offer help.

* If you have questions about using Ganzua, you may search existing posts at <https://github.com/latk/ganzua/discussions> and start a new discussion if necessary.
* If you have discovered a bug in Ganzua, please report it at <https://github.com/latk/ganzua/issues>.

Ganzua intends to maintain a backwards-compatible command line interface, and intends to use SemVer version numbers.

Only those parts of the CLI that are relevant for scripting are covered by this stability policy:

* commands that inspect or modify files
* machine-readable output, e.g. the schema of JSON output

For example, Ganzua might increment the "minor" version number if a new field is added to JSON output or if new command line options are added, and increment the "major" version if output fields are removed or new required command line arguments are added.

Out of scope are:

* interacting with the `ganzua` Python module
* Python versions or dependency versions used by Ganzua
* formatting of human-readable output (e.g. Markdown)
* formatting of error messages
* commands and flags that relate to help messages

<!-- ANCHOR_END: support -->

##  What does Ganzua mean?

The Spanish term *ganzúa* means lockpick. It is pronounced *gan-THU-a*.

This `ganzua` tool for interacting with Python dependency lockfiles
is unrelated to the [2004 cryptoanalysis tool of the same name](https://ganzua.sourceforge.net/en/index.html).

## What makes Ganzua special?

<!-- ANCHOR: usp -->

**Ganzua is not a general-purpose tool.**
It's focused solely on working with two modern Python project managers, uv and Poetry, and their native lockfile formats. In particular, there's no support for `requirements.txt`.

**Ganzua strives to be complete, compliant, and correct.**
Ganzua is 0% AI and 100% human expertise, informed by reading the relevant PEPs, docs, and the source code of relevant tools.
The tool is thoroughly tested with 100% branch coverage, and has seen extensive use in large-scale real-world projects.
Ganzua is intentionally stupid and avoids dangerous stuff like editing lockfiles or interacting with Git.

**Ganzua is designed for scripting.**
All subcommands are designed for JSON output first, with output that conforms to a stable schema.
Where appropriate, Ganzua offers an optional Markdown view on the same data, which lets scripts generate human-readable summaries.
Ganzua does not offer GitHub Actions, but it's really easy to integrate Ganzua into your CI workflows.

<!-- ANCHOR_END: usp -->

## License

<!-- ANCHOR: license -->

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

<!-- ANCHOR_END: license -->
