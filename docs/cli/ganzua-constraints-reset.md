# ganzua constraints reset

<!-- command output: ganzua help constraints reset --markdown --markdown-links={slug}.md -->

Usage: `ganzua constraints reset [OPTIONS] [PYPROJECT]`

Remove or relax any dependency version constraints from the `pyproject.toml`.

This can be useful for allowing uv/Poetry to update to the most recent versions,
ignoring the previous constraints. Approximate recipe:

```bash
ganzua constraints reset --to=minimum --backup=pyproject.toml.bak
uv lock --upgrade  # perform the upgrade
mv pyproject.toml.bak pyproject.toml  # restore old constraints
ganzua constraints bump
uv lock
```

The `PYPROJECT` argument should point to a `pyproject.toml` file,
or to a directory containing such a file.
If this argument is not specified,
the one in the current working directory will be used.

**Options:**

* `--backup PATH`
  Store a backup in this file.
* `--to [none|minimum]`
  How to reset constraints.
  * `none` (default): remove all constraints
  * `minimum`: set constraints to the currently locked minimum, removing upper bounds
* `--lockfile PATH`
  Where to load current versions from (for `--to=minimum`). Inferred if possible.
  * file: use the path as the lockfile
  * directory: use the lockfile in that directory
  * default: use the lockfile in the `PYPROJECT` directory
* `--help`
  Show this help message and exit.

<!-- command output end -->


## Examples

### Removing constraints

<!-- doctest: clean example -->

By default, `ganzua constraints reset` will remove all version constraints.
This is useful when we want `poetry lock`/`uv lock` to compute a completely unconstrainted, up-to-date dependency solution.

Let's set up an example with a `pyproject.toml` file.

```console
$ cp $CORPUS/new-uv-project/pyproject.toml $EXAMPLE/pyproject.toml
```

<details><summary><code>$ cat $EXAMPLE/pyproject.toml</code></summary>

```toml
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "annotated-types>=0.7.0",
    "typing-extensions>=4",
]
```

</details>

We can now reset the constraints and create a backup:

```console
$ ganzua constraints reset $EXAMPLE --backup=$EXAMPLE/old.pyproject.toml
$ ls $EXAMPLE
old.pyproject.toml
pyproject.toml
```

This edits the `pyproject.toml` file.
All dependencies are still present, but they no longer constrain any versions:

<details><summary><code>$ cat $EXAMPLE/pyproject.toml</code></summary>

```toml
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "annotated-types",
    "typing-extensions",
]
```

</details>

We can more directly compare the changes to the constriants via `ganzua constraints inspect`:

<details><summary>constraints in the backup</summary>
<!-- command output: ganzua constraints inspect $EXAMPLE/old.pyproject.toml --format=markdown -->

| package           | version |
|-------------------|---------|
| annotated-types   | >=0.7.0 |
| typing-extensions | >=4     |

<!-- command output end -->
</details>

<details><summary>constraints in the edited project</summary>
<!-- command output: ganzua constraints inspect $EXAMPLE/pyproject.toml --format=markdown -->

| package           | version |
|-------------------|---------|
| annotated-types   |         |
| typing-extensions |         |

<!-- command output end -->
</details>

### Removing constraints in extras and dependency groups

<!-- doctest: clean example -->

The `ganzua constraints reset` tool will also look into `[project.optional-dependencies]` and `dependency-groups`.

Let's set up a new example with a more complicated `pyproject.toml` file.

```console
$ cp $CORPUS/constraints-uv-pyproject.toml $EXAMPLE/pyproject.toml
```

<details><summary><code>$ cat $EXAMPLE/pyproject.toml</code></summary>

```toml
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "Typing.Extensions>=3,<4",  # moar type annotations
    "merrily-ignored",
    [42, "also ignored"],  # we ignore invalid junk
]

[project.optional-dependencies]
extra1 = [
    "annotated-types >=0.6.1, ==0.6.*",
]
extra2 = false  # known invalid
extra3 = ["ndr"]

[dependency-groups]
group-a = ["typing-extensions ~=3.4"]
group-b = [{include-group = "group-a"}, "annotated-types ~=0.6.1"]
```

</details>

Note that the file contains an invalid structure, such as an array where the schema would expect a string.

Running the reset succeeds.
Any errors in the file are ignored silently.

```console
$ ganzua constraints reset $EXAMPLE
```

The resulting `pyproject.toml` file is stripped of all dependency version constraints.

<details><summary><code>$ cat $EXAMPLE/pyproject.toml</code></summary>

```toml
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "Typing.Extensions",  # moar type annotations
    "merrily-ignored",
    [42, "also ignored"],  # we ignore invalid junk
]

[project.optional-dependencies]
extra1 = [
    "annotated-types",
]
extra2 = false  # known invalid
extra3 = ["ndr"]

[dependency-groups]
group-a = ["typing-extensions"]
group-b = [{include-group = "group-a"}, "annotated-types"]
```

</details>


### Removing constraints for Poetry

<!-- doctest: clean example -->

When using Poetry with dependencies in the `[tool.poetry]` table,
resetting a constraint will change it to `*`.

Let's set up a new example.
This example file also demonstrates Poetry dependency groups.

```console
$ cp $CORPUS/constraints-poetry-pyproject.toml $EXAMPLE/pyproject.toml
```

<details><summary><code>$ cat $EXAMPLE/pyproject.toml</code></summary>

```toml
[tool.poetry.dependencies]
Typing_Extensions = "^3.2"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "^3.4" }
already-unconstrained = "*"
```

</details>

We can now reset the constraints:

```console
$ ganzua constraints reset $EXAMPLE
```

The versions will now be set to `*`, including for dependencies in groups:

<!-- command output: ganzua constraints inspect $EXAMPLE/pyproject.toml --format=markdown -->

| package               | version | group/extra      |
|-----------------------|---------|------------------|
| already-unconstrained | *       | group `poetry-a` |
| typing-extensions     | *       |                  |
| typing-extensions     | *       | group `poetry-a` |

<!-- command output end -->

<details><summary><code>$ cat $EXAMPLE/pyproject.toml</code></summary>

```toml
[tool.poetry.dependencies]
Typing_Extensions = "*"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "*" }
already-unconstrained = "*"
```

</details>


### Resetting constraints to minimum


If we want to upgrade dependencies in a project, it's usually desirable to prevent unexpected downgrades.
Ganzua can assist here with the `--to=minimum` option.
Instead of removing all version constraints, we rewrite the constraints to use the currently locked version as a lower bound.

Let's set up an example **using UV**:

<!-- doctest: clean example -->

```console
$ cp $CORPUS/constraints-uv-pyproject.toml $EXAMPLE/pyproject.toml
```

Current constraints:

<!-- command output: ganzua constraints inspect $EXAMPLE/pyproject.toml --format=markdown -->

| package           | version         | group/extra                      |
|-------------------|-----------------|----------------------------------|
| annotated-types   | ==0.6.*,>=0.6.1 | extra `extra1`                   |
| annotated-types   | ~=0.6.1         | group `group-b`                  |
| merrily-ignored   |                 |                                  |
| ndr               |                 | extra `extra3`                   |
| typing-extensions | <4,>=3          |                                  |
| typing-extensions | ~=3.4           | group `group-a`, group `group-b` |

<!-- command output end -->

Current locked versions:

<!-- doctest: create uv lockfile $EXAMPLE/uv.lock -->

| name              | version |
|-------------------|---------|
| annotated-types   | 0.7.0   |
| example           | 0.2.0   |
| typing-extensions | 4.14.1  |

Now let's reset the constraints:

```console
$ ganzua constraints reset --to=minimum $EXAMPLE
```

The constraints in the `pyproject.toml` file have been reset to a lower bound with the locked version:

<!-- command output: ganzua constraints inspect $EXAMPLE/pyproject.toml --format=markdown -->

| package           | version  | group/extra                      |
|-------------------|----------|----------------------------------|
| annotated-types   | >=0.7.0  | extra `extra1`                   |
| annotated-types   | >=0.7.0  | group `group-b`                  |
| merrily-ignored   |          |                                  |
| ndr               |          | extra `extra3`                   |
| typing-extensions | >=4.14.1 |                                  |
| typing-extensions | >=4.14.1 | group `group-a`, group `group-b` |

<!-- command output end -->

<details><summary><code>$ cat $EXAMPLE/pyproject.toml</code></summary>

```toml
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "Typing.Extensions>=4.14.1",  # moar type annotations
    "merrily-ignored",
    [42, "also ignored"],  # we ignore invalid junk
]

[project.optional-dependencies]
extra1 = [
    "annotated-types>=0.7.0",
]
extra2 = false  # known invalid
extra3 = ["ndr"]

[dependency-groups]
group-a = ["typing-extensions>=4.14.1"]
group-b = [{include-group = "group-a"}, "annotated-types>=0.7.0"]
```

</details>

We can do the same **using Poetry**:

<!-- doctest: clean example -->

```console
$ cp $CORPUS/constraints-poetry-pyproject.toml $EXAMPLE/pyproject.toml
```

Current constraints:

<!-- command output: ganzua constraints inspect $EXAMPLE/pyproject.toml --format=markdown -->

| package               | version | group/extra      |
|-----------------------|---------|------------------|
| already-unconstrained | *       | group `poetry-a` |
| typing-extensions     | ^3.2    |                  |
| typing-extensions     | ^3.4    | group `poetry-a` |

<!-- command output end -->

Current locked versions:

<!-- doctest: create poetry lockfile $EXAMPLE/poetry.lock -->

| name              | version |
|-------------------|---------|
| annotated-types   | 0.7.0   |
| example           | 0.2.0   |
| typing-extensions | 4.14.1  |

<!-- command output end -->

Now let's reset the constraints:

```console
$ ganzua constraints reset --to=minimum $EXAMPLE
```

The constraints in the `pyproject.toml` file have been reset to a lower bound with the locked version:

<!-- command output: ganzua constraints inspect $EXAMPLE/pyproject.toml --format=markdown -->

| package               | version  | group/extra      |
|-----------------------|----------|------------------|
| already-unconstrained | *        | group `poetry-a` |
| typing-extensions     | >=4.14.1 |                  |
| typing-extensions     | >=4.14.1 | group `poetry-a` |

<!-- command output end -->


### Resolving the minimum version requires a lockfile

<!-- doctest: clean example -->

When we try to reset versions to their minimum but the project doesn't have a lockfile,
then we get an error.

```console
$ cp $CORPUS/new-poetry-project/pyproject.toml $EXAMPLE/pyproject.toml
$ ganzua constraints reset --to=minimum $EXAMPLE
Usage: ganzua constraints reset [OPTIONS] [PYPROJECT]
Try 'ganzua constraints reset --help' for help.

Error: Could not infer `--lockfile` for `${EXAMPLE}`.
Note: Using `--to=minimum` requires a `--lockfile`.
[command exited with status 2]
```

But this succeeds when passing an explicit lockfile, or to a directory containing a lockfile:

```console
$ ganzua constraints reset --to=minimum --lockfile=$CORPUS/new-uv-project/uv.lock $EXAMPLE
$ ganzua constraints reset --to=minimum --lockfile=$CORPUS/new-uv-project         $EXAMPLE
```

This also works if the lockfile can be inferred from the `pyproject.toml` file.

```console
$ cp $CORPUS/new-uv-project/uv.lock $EXAMPLE/uv.lock
$ ganzua constraints reset --to=minimum $EXAMPLE
```

### Inferring `pyproject.toml` location

<!-- doctest: clean example -->

Let's consider an empty example project:

```console
$ ls $EXAMPLE
```

Running Ganzua within this directory will fail, as there's no `pyproject.toml` file:

```console
$ env -C $EXAMPLE ganzua constraints reset
Usage: ganzua constraints reset [OPTIONS] [PYPROJECT]
Try 'ganzua constraints reset --help' for help.

Error: Did not find default `pyproject.toml`.
[command exited with status 2]
```

Once we add a `pyproject.toml`, it will be picked up implicitly,
and all oft he below Ganzua commands are equivalent.

```console
$ cp $CORPUS/old-uv-project/pyproject.toml $EXAMPLE/pyproject.toml
$ env -C $EXAMPLE ganzua constraints reset
$ env -C $EXAMPLE ganzua constraints reset pyproject.toml
$ env -C $EXAMPLE ganzua constraints reset .
$ ganzua constraints reset $EXAMPLE/pyproject.toml
$ ganzua constraints reset $EXAMPLE
```

That is, we can specify a directory or a file path,
and omit this argument entirely if we want to act on the project in the current working directory.
