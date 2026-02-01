# ganzua constraints bump

<!-- command output: ganzua help constraints bump --markdown --markdown-links={slug}.md -->

Usage: `ganzua constraints bump [OPTIONS] [PYPROJECT]`

Update `pyproject.toml` dependency constraints to match the lockfile.

Of course, the lockfile should always be a valid solution for the constraints.
But often, the constraints are somewhat relaxed.
This tool will *increment* the constraints to match the currently locked versions.
Specifically, the locked version becomes a lower bound for the constraint.

This tool will try to be as granular as the original constraint.
For example, given the old constraint `foo>=3.5` and the new version `4.7.2`,
the constraint would be updated to `foo>=4.7`.

The `PYPROJECT` argument should point to a `pyproject.toml` file,
or to a directory containing such a file.
If this argument is not specified,
the one in the current working directory will be used.

**Options:**

* `--lockfile PATH`
  Where to load versions from. Inferred if possible.
  * file: use the path as the lockfile
  * directory: use the lockfile in that directory
  * default: use the lockfile in the `PYPROJECT` directory
* `--backup PATH`
  Store a backup in this file.
* `--help`
  Show this help message and exit.

<!-- command output end -->

## Examples

The following examples illustrate how version bumping works.

The different version specifier operators are defined in [PEP-440](https://peps.python.org/pep-0440/), with the [up-to-date specifications on packaging.python.org](https://packaging.python.org/en/latest/specifications/version-specifiers/).

* `~=1.2.3` [compatible release examples](#compatible-release-examples)
* `==1.2.3` [strict version matching examples](#strict-version-matching-examples)
* `==1.*` [prefix version matching examples](#prefix-version-matching-examples)
* `!=1.2.3` [version exclusion examples](#version-exclusion-examples)
* `>=1.2.3` [lower version bound examples](#lower-version-bound-examples)
* `<=1.2.3`, `>1.2.3`, `<1.2.3` [ordered comparison examples](#ordered-comparison-examples)
* `===1.2.3+build123` [arbitrary equality examples](#arbitrary-equality-examples)

Certain combinations of operators are often used to describe SemVer constraints,
e.g. `>=1.2.3,<2` or `>=1.2.3,==1.*` (see [SemVer examples](#semver-examples)).

Poetry supports [certain additional operators](https://python-poetry.org/docs/dependency-specification/):

* `1.2.3` [strict version matching examples](#strict-version-matching-examples)
* `1.*` [prefix version matching examples](#prefix-version-matching-examples)
* `~1.2.3` [Poetry tilde examples](#poetry-tilde-examples)
* `^1.2.3` [SemVer examples](#semver-examples)

**Syntax** for example tables:

* The `locked` column shows the locked version in format `<package> <version>`, e.g. `foo 1.2.3`.
* The `old` and `new` column show the constraint before and after bumping.
  * may use PEP-508/PEP-440 expressions, e.g. `foo >=1.2.3`
  * may describe Poetry version constraints using a `<package> = <version>` format but without quoting that would appear in a TOML file, e.g. `foo = *`

### Basic examples

Will only bump packages that are present in the lockfile.
Other constraints are not affected:

<!-- doctest: check ganzua constraints bump -->

| locked         | old            | new            |
|----------------|----------------|----------------|
| `locked 1.2.3` | `other >=4,<5` | `other >=4,<5` |
| `locked 1.2.3` | `other = ^4`   | `other = ^4`   |

Bumping matches the granularity of the bounds that are currently present.

If there are no constraints for that package, bumping will not add any bounds:

<!-- doctest: check ganzua constraints bump -->

| locked          | old           | new           |
|-----------------|---------------|---------------|
| `package 1.2.3` | `package`     | `package`     |
| `package 1.2.3` | `package = *` | `package = *` |


### Lower version bound examples

When the **major** version changes, a `>=` bound is bumped with matching granularity:

<!-- doctest: check ganzua constraints bump -->

| locked               | old                    | new                    |
|----------------------|------------------------|------------------------|
| `major 7.1.2`        | `major>=4`             | `major>=7`             |
| `minor 7.1.2`        | `minor>=4.3`           | `minor>=7.1`           |
| `patch 7.1.2`        | `patch>=4.3.2`         | `patch>=7.1.2`         |
| `minor-poetry 7.1.2` | `minor-poetry = >=4.3` | `minor-poetry = >=7.1` |


When the **minor** or **patch** version changes, a `>=` bound is bumped with matching granularity.
Here, no changes to the `major` constraint are needed.
Granularity is determined based on how many version elements have been explicitly provided.
So whereas the versions `4` and `4.0` are semantically equivalent, they have different granularity.

<!-- doctest: check ganzua constraints bump -->

| locked               | old                      | new                      |
|----------------------|--------------------------|--------------------------|
| `major 4.5.6`        | `major>=4`               | `major>=4`               |
| `minor0 4.5.6`       | `minor0>=4.0`            | `minor0>=4.5`            |
| `minor 4.5.6`        | `minor>=4.3`             | `minor>=4.5`             |
| `patch 4.5.6`        | `patch>=4.3.2`           | `patch>=4.5.6`           |
| `minor-poetry 4.5.6` | `minor-poetry = >=4.3`   | `minor-poetry = >=4.5`   |
| `patch-poetry 4.5.6` | `patch-poetry = >=4.3.2` | `patch-poetry = >=4.5.6` |

Constraints may also be **downgraded** if this is necessary to match the locked version:

<!-- doctest: check ganzua constraints bump -->

| locked        | old            | new            |
|---------------|----------------|----------------|
| `major 4.5.6` | `major>=7`     | `major>=4`     |
| `minor 4.5.6` | `minor>=4.9`   | `minor>=4.5`   |
| `patch 4.5.6` | `patch>=4.5.9` | `patch>=4.5.6` |


### SemVer examples

Poetry has the `^` SemVer operator.
It is bumped the same way as `>=` bounds:

<!-- doctest: check ganzua constraints bump -->

| locked            | old                | new                |
|-------------------|--------------------|--------------------|
| `major 7.1.2`     | `major = ^4`       | `major = ^7`       |
| `minor 7.1.2`     | `minor = ^7.0`     | `minor = ^7.1`     |
| `patch 7.1.2`     | `patch = ^7.1.1`   | `patch = ^7.1.2`   |
| `downgrade 7.1.2` | `downgrade = ^9.8` | `downgrade = ^7.1` |

However, SemVer bounds are also frequently expressed via PEP-440 expressions.
For example, the Poetry bound `^4.1` can also be expressed via the following idioms:

* upper bounds `>=4.1,<5`
* version matching prefixes `>=4.1,==4.*`

**Upper bounds** will be bumped when they look like a SemVer bound (`>=N, <N+1`) and would be outdated by the new version:

<!-- doctest: check ganzua constraints bump -->

| locked         | old               | new               |
|----------------|-------------------|-------------------|
| `major 7.1.2`  | `major>=4,<5`     | `major>=7,<8`     |
| `minor0 7.1.2` | `minor0>=4.0,<5`  | `minor0>=7.1,<8`  |
| `minor 7.1.2`  | `minor>=4.9,<5`   | `minor>=7.1,<8`   |
| `patch 7.1.2`  | `patch>=4.0.1,<5` | `patch>=7.1.2,<8` |

<!-- TODO also support this:
| `downgrade 7.1.2` | `downgrade >=9.8,<10` | `downgrade>=7.1,<8` |
-->

However, upper bounds are not changed if they remain valid for the locked version:

<!-- doctest: check ganzua constraints bump -->

| locked                  | old                       | new                       |
|-------------------------|---------------------------|---------------------------|
| `minor-upgrade 4.5.6`   | `minor-upgrade>=4.3,<5`   | `minor-upgrade>=4.5,<5`   |
| `minor-downgrade 4.5.6` | `minor-downgrade>=4.9,<5` | `minor-downgrade>=4.5,<5` |
| `wide 7.1.2`            | `wide>=4.5,<9`            | `wide>=7.1,<9`            |

The **prefix version matching** SemVer idiom behaves more intuitively because each bound in the constraint will be bumped independently to match the new version:

<!-- doctest: check ganzua constraints bump -->

| locked                  | old                          | new                          |
|-------------------------|------------------------------|------------------------------|
| `major 7.1.2`           | `major>=4,==4.*`             | `major>=7,==7.*`             |
| `minor0 7.1.2`          | `minor0>=4.0,==4.*`          | `minor0>=7.1,==7.*`          |
| `minor 7.1.2`           | `minor>=4.9,==4.*`           | `minor>=7.1,==7.*`           |
| `minor-match 7.1.2`     | `minor-match>=4.9,==4.9.*`   | `minor-match>=7.1,==7.1.*`   |
| `patch 7.1.2`           | `patch>=4.0.1,==4.*`         | `patch>=7.1.2,==7.*`         |
| `downgrade 7.1.2`       | `downgrade >=9.8,==9.*`      | `downgrade>=7.1,==7.*`       |
| `minor-upgrade 4.5.6`   | `minor-upgrade>=4.3,==4.*`   | `minor-upgrade>=4.5,==4.*`   |
| `minor-downgrade 4.5.6` | `minor-downgrade>=4.9,==4.*` | `minor-downgrade>=4.5,==4.*` |


### Strict version matching examples

The `==` operator can be used for exact version matching (without `*` wildcards for [prefix matching](#prefix-version-matching-examples)).
Exact bounds will be bumped to match the locked version exactly.

The `==` operator is also implied when a Poetry version constraint doesn't use any operators.

<details><summary>expand PEP-440 examples</summary>

<!-- doctest: check ganzua constraints bump -->

| locked      | old          | new          |
|-------------|--------------|--------------|
| `foo 7.1.2` | `foo==4.3.2` | `foo==7.1.2` |
| `foo 7.1.2` | `foo==4.3`   | `foo==7.1.2` |
| `foo 7.1.2` | `foo==4`     | `foo==7.1.2` |
| `foo 7.1.2` | `foo==7`     | `foo==7.1.2` |
| `foo 7.1.2` | `foo==7.1`   | `foo==7.1.2` |
| `foo 7.1.2` | `foo==7.1.2` | `foo==7.1.2` |

</details>

<details><summary>expand Poetry examples</summary>

<!-- doctest: check ganzua constraints bump -->

| locked      | old           | new           |
|-------------|---------------|---------------|
| `foo 7.1.2` | `foo = 4.3.2` | `foo = 7.1.2` |
| `foo 7.1.2` | `foo = 4.3`   | `foo = 7.1.2` |
| `foo 7.1.2` | `foo = 4`     | `foo = 7.1.2` |
| `foo 7.1.2` | `foo = 7`     | `foo = 7.1.2` |
| `foo 7.1.2` | `foo = 7.1`   | `foo = 7.1.2` |
| `foo 7.1.2` | `foo = 7.1.2` | `foo = 7.1.2` |

</details>


### Prefix version matching examples

When the `==` operator is combined with `*` wildcards, it performs prefix matching.
Such constraints are updated with matching granularity.

The `==` operator is implied when a Poetry version constraint doesn't use any operators.

<details><summary>expand PEP-440 examples</summary>

<!-- doctest: check ganzua constraints bump -->

| locked      | old          | new          |
|-------------|--------------|--------------|
| `foo 7.1.2` | `foo==4.3.*` | `foo==7.1.*` |
| `foo 7.1.2` | `foo==4.*`   | `foo==7.*`   |
| `foo 7.1.2` | `foo==7.*`   | `foo==7.*`   |
| `foo 7.1.2` | `foo==7.0.*` | `foo==7.1.*` |
| `foo 7.1.2` | `foo==7.1.*` | `foo==7.1.*` |

</details>

<details><summary>expand Poetry examples</summary>

<!-- doctest: check ganzua constraints bump -->

| locked      | old           | new           |
|-------------|---------------|---------------|
| `foo 7.1.2` | `foo = 4.3.*` | `foo = 7.1.*` |
| `foo 7.1.2` | `foo = 4.*`   | `foo = 7.*`   |
| `foo 7.1.2` | `foo = 7.*`   | `foo = 7.*`   |
| `foo 7.1.2` | `foo = 7.0.*` | `foo = 7.1.*` |
| `foo 7.1.2` | `foo = 7.1.*` | `foo = 7.1.*` |

</details>

### Compatible release examples

The `~=` compatible release operator ([spec][spec-compatible-release]) is bumped the same way as [`>=` lower bounds](#lower-version-bound-examples):
it will be bumped so that it is a lower bound for the currently locked version, matching granularity.

Note that a `~=` compatible release clause needs to consist at least of `~=major.minor`.
A single element is insufficient.

See also the [Poetry `~` tilde operator](#poetry-tilde-examples).

[spec-compatible-release]: https://packaging.python.org/en/latest/specifications/version-specifiers/#compatible-release

<details><summary>expand PEP-440 examples</summary>

<!-- doctest: check ganzua constraints bump -->

| locked                  | old                      | new                      |
|-------------------------|--------------------------|--------------------------|
| `major 7.1.2`           | `major~=4.5`             | `major~=7.1`             |
| `minor0 4.5.6`          | `minor0~=4.0`            | `minor0~=4.5`            |
| `minor 4.5.6`           | `minor~=4.3`             | `minor~=4.5`             |
| `patch 4.5.6`           | `patch~=4.3.2`           | `patch~=4.5.6`           |
| `minor-poetry 4.5.6`    | `minor-poetry = ~=4.3`   | `minor-poetry = ~=4.5`   |
| `patch-poetry 4.5.6`    | `patch-poetry = ~=4.3.2` | `patch-poetry = ~=4.5.6` |
| `major-downgrade 4.5.6` | `major-downgrade~=7.9`   | `major-downgrade~=4.5`   |
| `minor-downgrade 4.5.6` | `minor-downgrade~=4.9`   | `minor-downgrade~=4.5`   |
| `patch-downgrade 4.5.6` | `patch-downgrade~=4.5.9` | `patch-downgrade~=4.5.6` |
| `noop 1.2.3`            | `noop~=1.2.3`            | `noop~=1.2.3`            |

</details>

### Poetry tilde examples

Tilde requirements ([spec][spec-poetry-tilde]) can only occur within the `[tool.poetry]` table.
They work similarly to [compatible release constraints](#compatible-release-examples),
but describe different version ranges.
Notably, a single segment like `~1` is allowed.

[spec-poetry-tilde]: https://python-poetry.org/docs/dependency-specification/#tilde-requirements

Poetry bumps such constraints the same way as [`>=` lower version bounds](#lower-version-bound-examples).

<details><summary>expand Poetry examples</summary>

<!-- doctest: check ganzua constraints bump -->

| locked                  | old                        | new                        |
|-------------------------|----------------------------|----------------------------|
| `major 7.1.2`           | `major = ~4`               | `major = ~7`               |
| `major 7.1.2`           | `major = ~4.5`             | `major = ~7.1`             |
| `minor0 4.5.6`          | `minor0 = ~4.0`            | `minor0 = ~4.5`            |
| `minor 4.5.6`           | `minor = ~4.3`             | `minor = ~4.5`             |
| `patch 4.5.6`           | `patch = ~4.3.2`           | `patch = ~4.5.6`           |
| `major-downgrade 4.5.6` | `major-downgrade = ~7`     | `major-downgrade = ~4`     |
| `major-downgrade 4.5.6` | `major-downgrade = ~7.9`   | `major-downgrade = ~4.5`   |
| `minor-downgrade 4.5.6` | `minor-downgrade = ~4.9`   | `minor-downgrade = ~4.5`   |
| `patch-downgrade 4.5.6` | `patch-downgrade = ~4.5.9` | `patch-downgrade = ~4.5.6` |
| `noop 1.2.3`            | `noop = ~1.2.3`            | `noop = ~1.2.3`            |
| `noop 1.2.3`            | `noop = ~1.2`              | `noop = ~1.2`              |
| `noop 1.2.3`            | `noop = ~1`                | `noop = ~1`                |

</details>

### Version exclusion examples

The `!=` version exclusion clause ([spec][spec-version-exclusion]) is the inverse of `==` version matching.
It can be used to exclude specific versions like `!=1.2.3` or prefixes like `!=1.2.*`.

[spec-version-exclusion]: https://packaging.python.org/en/latest/specifications/version-specifiers/#version-exclusion

When Ganzua bumps a version exclusion specifier, the specifier will be retained as-is, unless it would exclude the currently locked version.

<details><summary>exclusions are kept by default</summary>

<!-- doctest: check ganzua constraints bump -->

| locked      | old          | new          |
|-------------|--------------|--------------|
| `foo 7.1.2` | `foo!=4.3.2` | `foo!=4.3.2` |
| `foo 7.1.2` | `foo!=4.*`   | `foo!=4.*`   |
| `foo 7.1.2` | `foo!=7.9.*` | `foo!=7.9.*` |
| `foo 7.1.2` | `foo!=7.0.1` | `foo!=7.0.1` |

</details>

<details><summary>exclusions are removed if they would exclude the current version</summary>

<!-- doctest: check ganzua constraints bump -->

| locked      | old          | new   |
|-------------|--------------|-------|
| `foo 7.1.2` | `foo!=7.*`   | `foo` |
| `foo 7.1.2` | `foo!=7.1.*` | `foo` |
| `foo 7.1.2` | `foo!=7.1.2` | `foo` |

</details>


### Arbitrary equality examples

The `===` arbitrary equality comparison ([spec][spec-arbitrary-equality]) matches only an exact version, without any semantic interpretation of the version number.

[spec-arbitrary-equality]: https://packaging.python.org/en/latest/specifications/version-specifiers/#arbitrary-equality

When Ganzua bumps arbitrary equality clauses, it always sets the currently locked version.
Ganzua requires that the currently locked version is valid, but allows the old version constraint to contain an invalid version number.

<details><summary>expand examples</summary>

<!-- doctest: check ganzua constraints bump -->

| locked                | old                     | new                     |
|-----------------------|-------------------------|-------------------------|
| `foo 7.1.2.post1+abc` | `foo===7.1.2`           | `foo===7.1.2.post1+abc` |
| `foo 7.1.2`           | `foo===7.1.2.post1+abc` | `foo===7.1.2`           |
| `foo 7.1.2`           | `foo===whatever`        | `foo===7.1.2`           |
| `unmodified 7.1.2`    | `unmodified===7.1.2`    | `unmodified===7.1.2`    |

<!-- TODO: also support invalid locked versions if possible
| `foo whatever`        | `foo===0.1.2`           | `foo===whatever`        |
-->

</details>

### Ordered comparison examples

The version constraint operators `<=`, `<`, and `>` ([spec][spec-inclusive-ordered-comparison]) cannot be bumped meaningfully.
Ganzua will retain them as-is if they allow the locked version, else remove them.

[spec-inclusive-ordered-comparison]: https://packaging.python.org/en/latest/specifications/version-specifiers/#inclusive-ordered-comparison

<details><summary>expand examples</summary>

<!-- doctest: check ganzua constraints bump -->

| locked      | old        | new        |
|-------------|------------|------------|
| `foo 7.1.2` | `foo>4`    | `foo>4`    |
| `foo 7.1.2` | `foo>8`    | `foo`      |
| `foo 7.1.2` | `foo<5`    | `foo`      |
| `foo 7.1.2` | `foo<8`    | `foo<8`    |
| `foo 7.1.2` | `foo<=5`   | `foo`      |
| `foo 7.1.2` | `foo<=8`   | `foo<=8`   |
| `foo 7.1.2` | `foo<=7.1` | `foo`      |
| `foo 7.1.2` | `foo<=7.2` | `foo<=7.2` |

</details>
