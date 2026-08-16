# Filters

Filters can be used to restrict Ganzua to operate only on certain dependencies.
Which filters are supported depends on the exact subcommand.

* [`ganzua inspect`](cli/ganzua-inspect.md) (`--filter`)\
  Select which locked packages are shown in the output.\
  Added as `--name` in *Ganzua 0.4.0*, renamed to `--filter` in *Ganzua NEXT*.

* [`ganzua diff`](cli/ganzua-diff.md) (`--filter`)\
  Select which locked packages are included in the diff.\
  Added as `--name` in *Ganzua 0.4.0*, renamed to `--filter` in *Ganzua NEXT*.

* [`ganzua constraints inspect`](cli/ganzua-constraints-inspect.md) (`--filter`)\
  Select which constraints are shown in the output.\
  Added as `--name` in *Ganzua 0.4.0*, renamed to `--filter` in *Ganzua NEXT*.

* [`ganzua constraints bump`](cli/ganzua-constraints-bump.md) (`--filter`)\
  Select which constraints are edited.\
  Added as `--name` in *Ganzua 0.4.0*, renamed to `--filter` in *Ganzua NEXT*.

* [`ganzua constraints reset`](cli/ganzua-constraints-reset.md) (`--filter`)\
  Select which constraints are edited.\
  Added as `--name` in *Ganzua 0.4.0*, renamed to `--filter` in *Ganzua NEXT*.

The following sections describe
the [syntax of filters](#syntax),
[how filters are evaluated](#evaluation),
and provide [examples](#examples).

## Syntax

A PEG-style grammar for the filter syntax would look as follows:

> filter → ws<sup>?</sup> rule ws<sup>?</sup> ( `,` ws<sup>?</sup> rule ws<sup>?</sup> )<sup>\*</sup>
>
> rule<sub>Lockfile</sub> → `!`<sup>?</sup> pattern
>
> rule<sub>Constraint</sub> → `!`<sup>?</sup> ( pattern ( ws qualifier )<sup>?</sup> | qualifier )
>
> qualifier → ( `extra:` pattern | `group:` pattern )
>
> pattern → ( literal | `*` | `?` )<sup>+</sup>
>
> literal → `/[a-zA-Z0-9._-]+/`
>
> ws → `/\s+/`

A **filter** consists of one or more rules, separated by comma.
Trailing commas are not allowed.
Each rule may be surrounded by whitespace.

Each **rule** consists of a name pattern and/or further qualifiers.
A **negated rule** has a leading `!` exclamation mark.
There may not be any space between the exclamation mark and the rest of the rule.

Rules come in two flavors:
A **lockfile rule** always consists of just a name pattern.
A **constraint rule** may consist of just a name pattern, a name pattern followed by a qualifier, or just a qualifier (which implies `*` as the name pattern).

A **qualifier** is a labeled pattern that either matches on an `extra` or `group` rather than on a constraint name.

Each **pattern** is a Unix glob expression, similar to what is supported in `.gitignore` files.
A pattern can contain literal content, `*` asterisk metacharacters, and `?` question mark metacharacters.
The pattern must not be empty.

The **`*` asterisk metacharacter** matches zero or more arbitrary characters.

The **`?` question mark metacharacter** matches a single arbitrary character.

**Literal content** can only consist of ASCII letters, ASCII digits, and PyPI name separators (`._-`).
Filters are only used to match names (e.g. PyPI package names), so literal content is matched in a normalized manner.
Literal content is not case sensitive, so the patterns `A` and `a` are equivalent.
Separators all match each other as per the Python packaging name normalization rules,
so the patterns `a_b`, `a.b`, and `a--b` are all equivalent.

Differences to `.gitignore`:

* filter rules are separated by commas, not by newlines
* comments are not supported
* escapes are not needed – metacharacters can never occur in a name
* no special rules for directory separators – slashes can never occur in a name
* other fnmatch syntax is not supported (see below)
* no `**` double asterisk metacharacter

Differences to fnmatch(3), glob(3), or glob(7):

* no character classes `[abc]`, ranges `[a-z]`, or complementation `[!a-z]` (also called *bracket expressions*)
* no brace expansion `{a,b,c}-{1,2,3}`
* no special handling for leading `.` periods – names can never start with a separator
* matching is always case-insensitive

References:

* Python package name format and normalization: <https://packaging.python.org/en/latest/specifications/name-normalization/>
* gitignore pattern format: <https://git-scm.com/docs/gitignore#_pattern_format>
* fnmatch(3): <https://man7.org/linux/man-pages/man3/fnmatch.3.html>
* glob(3): <https://man7.org/linux/man-pages/man3/glob.3.html>
* glob(7): <https://man7.org/linux/man-pages/man7/glob.7.html>
* fnmatch() in POSIX.1-2024: <https://pubs.opengroup.org/onlinepubs/9799919799/functions/fnmatch.html> (links to syntax specifications)


## Evaluation

When matching an item against a filter, all rules are evaluated in order.
When a normal rule matches, the item is explicitly included.
When a negated rule matches, the item is explicitly excluded.
An item can flip between included and excluded state arbitrarily often, and only the final state matters.
Filter matching does not short-circuit.

If a filter contains at least one normal (non-negated) rule, each item is excluded by default, and at least one of the normal rules must match.
This is as-if such a filter started with a `!*` pattern.
If a filter only contains negated rales, names are included by default, and the negated patterns can exclude names.
This is as-if the filter started with a `*` rule.

These semantics are exactly [how glob patterns work in ripgrep](https://github.com/BurntSushi/ripgrep/blob/4519153e5e461527f4bca45b042fff45c4ec6fb9/GUIDE.md#manual-filtering-globs).

A constraint rule can consist of a plain pattern which matches the dependency name,
and/or qualifiers which are patterns for matching group or extra names.
If a qualifier is not specified, it will match everything – qualifiers only narrow a rule, never broaden it.
For example, the rule `*` is a name-pattern which matches all constraints.
The rules `* group:*` or just `group:*` match any constraints within any dependency group,
but not constraints outside of a dependency group.
If the same constraint is part of multiple dependency groups,
a `group:…` qualifier will match if any group name matches.
This matters especially for negated rules in the presence of the `include-group` operator.

## Examples

<!-- doctest: clean example -->

Let's consider a project with the following lockfile:

<details><summary>full lockfile contents</summary>

<!-- doctest: create uv lockfile $EXAMPLE/uv.lock -->

| name              | version |
|-------------------|---------|
| annotated-types   | 0.7.0   |
| click             | 8.3.1   |
| colorama          | 0.4.6   |
| coverage          | 7.12.0  |
| dirty-equals      | 0.11    |
| executing         | 2.2.1   |
| idna              | 3.11    |
| iniconfig         | 2.3.0   |
| inline-snapshot   | 0.31.1  |
| multidict         | 6.7.0   |
| mypy              | 1.18.2  |
| mypy-extensions   | 1.1.0   |
| packaging         | 25.0    |
| pluggy            | 1.6.0   |
| propcache         | 0.4.1   |
| pydantic          | 2.12.4  |
| pydantic-core     | 2.41.5  |
| pygments          | 2.19.2  |
| pytest            | 9.0.1   |
| pytest-cov        | 7.0.0   |
| tomlkit           | 0.13.3  |
| typing-extensions | 4.15.0  |
| typing-inspection | 0.4.2   |
| yarl              | 1.22.0  |

</details>

We can use a name filter to select one or more specific packages from the lockfile:

<details><summary><code>$ ganzua inspect $EXAMPLE --filter=pydantic --format=markdown</code></summary>

```
| package  | version |
|----------|---------|
| pydantic | 2.12.4  |
```

</details>

<details><summary><code>$ ganzua inspect $EXAMPLE --filter=pydantic,mypy,pytest-cov --format=markdown</code></summary>

```
| package    | version |
|------------|---------|
| mypy       | 1.18.2  |
| pydantic   | 2.12.4  |
| pytest-cov | 7.0.0   |
```

</details>

We can use glob patterns to select all packages that start with `py`:

<details><summary><code>$ ganzua inspect $EXAMPLE --filter='py*' --format=markdown</code></summary>

```
| package       | version |
|---------------|---------|
| pydantic      | 2.12.4  |
| pydantic-core | 2.41.5  |
| pygments      | 2.19.2  |
| pytest        | 9.0.1   |
| pytest-cov    | 7.0.0   |
```

</details>

Or all packages that contain `py` but do not start with `py`:

<details><summary><code>$ ganzua inspect $EXAMPLE --filter='*py*, !py*' --format=markdown</code></summary>

```
| package         | version |
|-----------------|---------|
| mypy            | 1.18.2  |
| mypy-extensions | 1.1.0   |
```

</details>

Using the question mark operator, we can select all packages that have a 4-letter name:

<details><summary><code>$ ganzua inspect $EXAMPLE --filter='????' --format=markdown</code></summary>

```
| package | version |
|---------|---------|
| idna    | 3.11    |
| mypy    | 1.18.2  |
| yarl    | 1.22.0  |
```

</details>

When only using negated patterns, results are included by default.
Here, we exclude all patterns that contain a hyphen, or start with the letters `p` or `c`:

<details><summary><code>$ ganzua inspect $EXAMPLE --filter='!*-*, !p*, !c*' --format=markdown</code></summary>

```
| package   | version |
|-----------|---------|
| executing | 2.2.1   |
| idna      | 3.11    |
| iniconfig | 2.3.0   |
| multidict | 6.7.0   |
| mypy      | 1.18.2  |
| tomlkit   | 0.13.3  |
| yarl      | 1.22.0  |
```

</details>

Filters are case-insensitive, and hyphens/underscores/periods are all equivalent.
Thus, all of these filters produce the same results:

<!-- doctest: compare output -->

* `$ ganzua inspect $EXAMPLE --filter='*ex*,!*-*' --format=markdown`
* `$ ganzua inspect $EXAMPLE --filter='*EX*,!*...*' --format=markdown`
* `$ ganzua inspect $EXAMPLE --filter='*eX*,!*_*' --format=markdown`

<details><summary>output for the above commands</summary>

```
| package   | version |
|-----------|---------|
| executing | 2.2.1   |
```

</details>

Some further filter syntax details that describe edge cases:

<details><summary>rules may be surrounded by spaces</summary>

```console
$ ganzua inspect $EXAMPLE --filter='  foo , bar, pytest  ' --format=markdown
| package | version |
|---------|---------|
| pytest  | 9.0.1   |
```

</details>

<details><summary>filters must not be empty</summary>

```console
$ ganzua inspect $EXAMPLE --filter='' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--filter': expected filter pattern
at offset 0 (EOF):
  |
  |^
[command exited with status 2]
```

```console
$ ganzua inspect $EXAMPLE --filter='foo,' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--filter': expected filter pattern
at offset 4 (EOF):
  |foo,
  |    ^
[command exited with status 2]
```

</details>

<details><summary>syntax errors</summary>

```console
$ ganzua inspect $EXAMPLE --filter='must not contain spaces' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--filter': unexpected content after filter rule
at offset 5 (char 'n' U+006E LATIN SMALL LETTER N):
  |must not contain spaces
  |     ^
[command exited with status 2]
```

```console
$ ganzua inspect $EXAMPLE --filter='/slashes/not/supported/' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--filter': expected filter pattern
at offset 0 (char '/' U+002F SOLIDUS):
  |/slashes/not/supported/
  |^
[command exited with status 2]
```

```console
$ ganzua inspect $EXAMPLE --filter='Ÿñiçøðœ' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--filter': expected filter pattern
at offset 0 (char 'Ÿ' U+0178 LATIN CAPITAL LETTER Y WITH DIAERESIS):
  |Ÿñiçøðœ
  |^
[command exited with status 2]
```

</details>

<details><summary>Bracket expressions and brace expansion are not supported</summary>

Conventional fnmatch syntax allows character classes like `[a-z]` or `[!a-z]`.
This doesn't seem overly helpful for matching package names, so hasn't been implemented yet.

```console
$ ganzua inspect $EXAMPLE --filter='ex[a-z]mple' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--filter': bracket expressions not supported
at offset 2 (char '[' U+005B LEFT SQUARE BRACKET):
  |ex[a-z]mple
  |  ^
[command exited with status 2]
```

Similarly, brace expansion is not supported.
Instead, it's usually possible to write multiple separate filters.

```console
$ ganzua inspect $EXAMPLE --filter='foo{,-bar}' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--filter': brace expansion not supported
at offset 3 (char '{' U+007B LEFT CURLY BRACKET):
  |foo{,-bar}
  |   ^
[command exited with status 2]
```

</details>

The `--name` option is a deprecated alias for `--filter`:

<details><summary><code>$ ganzua inspect $EXAMPLE --name pydantic --format=markdown</code></summary>

```
DeprecationWarning: The option 'name' is deprecated. Use `--filter` instead of `--name`.
| package  | version |
|----------|---------|
| pydantic | 2.12.4  |
```

</details>

## Constraint rule examples

<!-- doctest: clean example -->

Let's consider a project with the following `pyproject.toml` file:

<!--

```console
$ cp $CORPUS/constraint-rule-pyproject.toml $EXAMPLE/pyproject.toml
```

-->

<details open><summary><code>$ cat $EXAMPLE/pyproject.toml</code></summary>

```toml
[project]
name = "example"
description = "demo for filters with constraint rules"
version = "0.0.0"
requires-python = ">=3.14"
dependencies = [
  "pydantic>=2.13.4",
]

[project.optional-dependencies]
db = ["sqlalchemy>=2.0.52"]
server = ["fastapi>=0.141.1"]

[dependency-groups]
dev = [{include-group = "test"}, {include-group = "types"}]
test = ["pytest>=9.1.1", "inline-snapshot>=0.35.4"]
types = ["mypy>=2.3.1"]
chores = ["towncrier>=25.8.0"]
```

</details>

By default, we'll see all dependencies:

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --format=markdown</code></summary>

```
| package         | version   | group/extra                |
|-----------------|-----------|----------------------------|
| fastapi         | >=0.141.1 | extra `server`             |
| inline-snapshot | >=0.35.4  | group `dev`, group `test`  |
| mypy            | >=2.3.1   | group `dev`, group `types` |
| pydantic        | >=2.13.4  |                            |
| pytest          | >=9.1.1   | group `dev`, group `test`  |
| sqlalchemy      | >=2.0.52  | extra `db`                 |
| towncrier       | >=25.8.0  | group `chores`             |
```

</details>

Name filters work across extras and dependencies:

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --filter='py*' --format=markdown</code></summary>

```
| package  | version  | group/extra               |
|----------|----------|---------------------------|
| pydantic | >=2.13.4 |                           |
| pytest   | >=9.1.1  | group `dev`, group `test` |
```

</details>

Can use qualifier rules to select just a certain extra or group:

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --filter='extra:db' --format=markdown</code></summary>

```
| package    | version  | group/extra |
|------------|----------|-------------|
| sqlalchemy | >=2.0.52 | extra `db`  |
```

</details>

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --filter='group:dev' --format=markdown</code></summary>

```
| package         | version  | group/extra                |
|-----------------|----------|----------------------------|
| inline-snapshot | >=0.35.4 | group `dev`, group `test`  |
| mypy            | >=2.3.1  | group `dev`, group `types` |
| pytest          | >=9.1.1  | group `dev`, group `test`  |
```

</details>

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --filter='group:test' --format=markdown</code></summary>

```
| package         | version  | group/extra               |
|-----------------|----------|---------------------------|
| inline-snapshot | >=0.35.4 | group `dev`, group `test` |
| pytest          | >=9.1.1  | group `dev`, group `test` |
```

</details>

Qualifiers themselves can take patterns:

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --filter='group:t*' --format=markdown</code></summary>

```
| package         | version  | group/extra                |
|-----------------|----------|----------------------------|
| inline-snapshot | >=0.35.4 | group `dev`, group `test`  |
| mypy            | >=2.3.1  | group `dev`, group `types` |
| pytest          | >=9.1.1  | group `dev`, group `test`  |
```

</details>

Wildcard qualifiers can be used to select "any extra" or "any group":

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --filter='group:*' --format=markdown</code></summary>

```
| package         | version  | group/extra                |
|-----------------|----------|----------------------------|
| inline-snapshot | >=0.35.4 | group `dev`, group `test`  |
| mypy            | >=2.3.1  | group `dev`, group `types` |
| pytest          | >=9.1.1  | group `dev`, group `test`  |
| towncrier       | >=25.8.0 | group `chores`             |
```

</details>

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --filter='extra:*' --format=markdown</code></summary>

```
| package    | version   | group/extra    |
|------------|-----------|----------------|
| fastapi    | >=0.141.1 | extra `server` |
| sqlalchemy | >=2.0.52  | extra `db`     |
```

</details>

Can select main dependencies by excluding any extras or groups:

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --filter='!extra:*, !group:*' --format=markdown</code></summary>

```
| package  | version  |
|----------|----------|
| pydantic | >=2.13.4 |
```

</details>

Can combine name patterns with qualifiers.
For example, can select all `py*` dependencies form the dev-group:

<details><summary><code>$ ganzua constraints inspect $EXAMPLE --filter='py* group:dev' --format=markdown</code></summary>

```
| package | version | group/extra               |
|---------|---------|---------------------------|
| pytest  | >=9.1.1 | group `dev`, group `test` |
```

</details>

Qualifier-related syntax errors:

<details><summary>Qualifier cannot come before name</summary>

```console
$ ganzua constraints inspect $EXAMPLE --filter='group:dev py*'
Usage: ganzua constraints inspect [OPTIONS] [PYPROJECT]
Try 'ganzua constraints inspect --help' for help.

Error: Invalid value for '--filter': unexpected content after filter rule
at offset 10 (char 'p' U+0070 LATIN SMALL LETTER P):
  |group:dev py*
  |          ^
[command exited with status 2]
```

</details>

<details><summary>Unknown qualifiers are rejected</summary>

```console
$ ganzua constraints inspect $EXAMPLE --filter='foo:bar'
Usage: ganzua constraints inspect [OPTIONS] [PYPROJECT]
Try 'ganzua constraints inspect --help' for help.

Error: Invalid value for '--filter': unexpected content after filter rule
at offset 3 (char ':' U+003A COLON):
  |foo:bar
  |   ^
[command exited with status 2]
```

```console
$ ganzua constraints inspect $EXAMPLE --filter='* foo:bar'
Usage: ganzua constraints inspect [OPTIONS] [PYPROJECT]
Try 'ganzua constraints inspect --help' for help.

Error: Invalid value for '--filter': unexpected content after filter rule
at offset 2 (char 'f' U+0066 LATIN SMALL LETTER F):
  |* foo:bar
  |  ^
[command exited with status 2]
```

</details>

<details><summary>Qualifiers cannot be repeated</summary>

```console
$ ganzua constraints inspect $EXAMPLE --filter='group:dev group:test'
Usage: ganzua constraints inspect [OPTIONS] [PYPROJECT]
Try 'ganzua constraints inspect --help' for help.

Error: Invalid value for '--filter': unexpected content after filter rule
at offset 10 (char 'g' U+0067 LATIN SMALL LETTER G):
  |group:dev group:test
  |          ^
[command exited with status 2]
```

</details>

<details><summary>Invalid characters</summary>

```console
$ ganzua constraints inspect $EXAMPLE --filter='/foo/bar'
Usage: ganzua constraints inspect [OPTIONS] [PYPROJECT]
Try 'ganzua constraints inspect --help' for help.

Error: Invalid value for '--filter': expected filter pattern or qualifier
at offset 0 (char '/' U+002F SOLIDUS):
  |/foo/bar
  |^
[command exited with status 2]
```

</details>

<details><summary>Qualifier pattern must not be empty</summary>

```console
$ ganzua constraints inspect $EXAMPLE --filter='group: ,*'
Usage: ganzua constraints inspect [OPTIONS] [PYPROJECT]
Try 'ganzua constraints inspect --help' for help.

Error: Invalid value for '--filter': expected pattern
at offset 6 (char ' ' U+0020 SPACE):
  |group: ,*
  |      ^
[command exited with status 2]
```

</details>

<details><summary>Lockfile filters cannot have qualifiers</summary>

```console
$ ganzua inspect $EXAMPLE --filter='group:dev'
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--filter': unexpected content after filter rule
at offset 5 (char ':' U+003A COLON):
  |group:dev
  |     ^
[command exited with status 2]
```

</details>
