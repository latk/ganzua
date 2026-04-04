# Filters

Filters can be used to restrict Ganzua to operate only on certain dependencies.
Which filters are supported depends on the exact subcommand.

* [`ganzua inspect`](cli/ganzua-inspect.md) (`--name`)\
  Select which packages are shown in the output.\
  Added in *Ganzua NEXT*.

* [`ganzua diff`](cli/ganzua-diff.md) (`--name`)\
  Select which packages are included in the diff.\
  Added in *Ganzua NEXT*.

* [`ganzua constraints inspect`](cli/ganzua-constraints-inspect.md) (`--name`)\
  Select which constraints are shown in the output.\
  Added in *Ganzua NEXT*.

* [`ganzua constraints bump`](cli/ganzua-constraints-bump.md) (`--name`)\
  Select which constraints are edited.\
  Added in *Ganzua NEXT*.

* [`ganzua constraints reset`](cli/ganzua-constraints-reset.md) (`--name`)\
  Select which constraints are edited.\
  Added in *Ganzua NEXT*.

The following sections describe
the [syntax of filters](#syntax),
[how filters are evaluated](#evaluation),
and provide [examples](#examples).

## Syntax

A PEG-style grammar for the filter syntax would look as follows:

> filter → ws<sup>?</sup> pattern ws<sup>?</sup> ( `,` ws<sup>?</sup> filter ws<sup>?</sup> )<sup>\*</sup>
>
> pattern → `!`<sup>?</sup> ( literal | `*` | `?` )<sup>+</sup>
>
> literal → `/[a-zA-Z0-9._-]+/`
>
> ws → `/\s+/`

A **filter** consists of one or more glob patterns, separated by comma.
Trailing commas are not allowed.
Each pattern may be surrounded by whitespace.

Each **pattern** is a Unix glob expression, similar to what is supported in `.gitignore` files.
A pattern can contain literal content, `*` asterisk metacharacters, and `?` question mark metacharacters.
The pattern must not be empty.

A **negated pattern** has a leading `!` exclamation mark.
There may not be any space between the exclamation mark and the rest of the pattern.

The **`*` asterisk metacharacter** matches zero or more arbitrary characters.

The **`?` question mark metacharacter** matches a single arbitrary character.

**Literal content** can only consist of ASCII letters, ASCII digits, and PyPI name separators (`._-`).
Filters are only used to match names (e.g. PyPI package names), so literal content is matched in a normalized manner.
Literal content is not case sensitive, so the patterns `A` and `a` are equivalent.
Separators all match each other as per the Python packaging name normalization rules,
so the patterns `a_b`, `a.b`, and `a--b` are all equivalent.

Differences to `.gitignore`:

* filter patterns are separated by commas, not by newlines
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

When matching a name against a filter, all patterns are evaluated in order.
When a normal pattern matches, the name is explicitly included.
When a negated pattern matches, the name is explicitly excluded.
A name can flip between included and excluded state arbitrarily often, and only the final state matters.
Filter matching does not short-circuit.

If a filter contains at least one normal (non-negated) pattern, each name is excluded by default, and at least one of the normal patterns must match.
This is as-if such a filter started with a `!*` pattern.
If a filter only contains negated patterns, names are included by default, and the negated patterns can exclude names.
This is as-if the filter started with a `*` pattern.

These semantics are exactly how glob patterns work in ripgrep: <https://github.com/BurntSushi/ripgrep/blob/4519153e5e461527f4bca45b042fff45c4ec6fb9/GUIDE.md#manual-filtering-globs>.

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

<details><summary><code>$ ganzua inspect $EXAMPLE --name=pydantic --format=markdown</code></summary>

```
| package  | version |
|----------|---------|
| pydantic | 2.12.4  |
```

</details>

<details><summary><code>$ ganzua inspect $EXAMPLE --name=pydantic,mypy,pytest-cov --format=markdown</code></summary>

```
| package    | version |
|------------|---------|
| mypy       | 1.18.2  |
| pydantic   | 2.12.4  |
| pytest-cov | 7.0.0   |
```

</details>

We can use glob patterns to select all packages that start with `py`:

<details><summary><code>$ ganzua inspect $EXAMPLE --name='py*' --format=markdown</code></summary>

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

<details><summary><code>$ ganzua inspect $EXAMPLE --name='*py*, !py*' --format=markdown</code></summary>

```
| package         | version |
|-----------------|---------|
| mypy            | 1.18.2  |
| mypy-extensions | 1.1.0   |
```

</details>

Using the question mark operator, we can select all packages that have a 4-letter name:

<details><summary><code>$ ganzua inspect $EXAMPLE --name='????' --format=markdown</code></summary>

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

<details><summary><code>$ ganzua inspect $EXAMPLE --name='!*-*, !p*, !c*' --format=markdown</code></summary>

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

* `$ ganzua inspect $EXAMPLE --name='*ex*,!*-*' --format=markdown`
* `$ ganzua inspect $EXAMPLE --name='*EX*,!*...*' --format=markdown`
* `$ ganzua inspect $EXAMPLE --name='*eX*,!*_*' --format=markdown`

<details><summary>output for the above commands</summary>

```
| package   | version |
|-----------|---------|
| executing | 2.2.1   |
```

</details>

Some further filter syntax details that describe edge cases:

<details><summary>filters may be surrounded by spaces</summary>

```console
$ ganzua inspect $EXAMPLE --name='  foo , bar, pytest  ' --format=markdown
| package | version |
|---------|---------|
| pytest  | 9.0.1   |
```

</details>

<details><summary>filters must not be empty</summary>

```console
$ ganzua inspect $EXAMPLE --name='' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--name': expected filter pattern
at offset 0 (EOF):
  |
  |^
[command exited with status 2]
```

```console
$ ganzua inspect $EXAMPLE --name='foo,' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--name': expected filter pattern
at offset 4 (EOF):
  |foo,
  |    ^
[command exited with status 2]
```

</details>

<details><summary>syntax errors</summary>

```console
$ ganzua inspect $EXAMPLE --name='must not contain spaces' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--name': unexpected content after filter pattern
at offset 5 (char 'n' U+006E LATIN SMALL LETTER N):
  |must not contain spaces
  |     ^
[command exited with status 2]
```

```console
$ ganzua inspect $EXAMPLE --name='/slashes/not/supported/' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--name': expected filter pattern
at offset 0 (char '/' U+002F SOLIDUS):
  |/slashes/not/supported/
  |^
[command exited with status 2]
```

```console
$ ganzua inspect $EXAMPLE --name='Ÿñiçøðœ' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--name': expected filter pattern
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
$ ganzua inspect $EXAMPLE --name='ex[a-z]mple' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--name': bracket expressions not supported
at offset 2 (char '[' U+005B LEFT SQUARE BRACKET):
  |ex[a-z]mple
  |  ^
[command exited with status 2]
```

Similarly, brace expansion is not supported.
Instead, it's usually possible to write multiple separate filters.

```console
$ ganzua inspect $EXAMPLE --name='foo{,-bar}' --format=markdown
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Invalid value for '--name': brace expansion not supported
at offset 3 (char '{' U+007B LEFT CURLY BRACKET):
  |foo{,-bar}
  |   ^
[command exited with status 2]
```

</details>
