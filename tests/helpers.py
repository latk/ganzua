import pathlib
import typing as t

import pytest

CLICK_ERROR = 2
"""The exit code used by Click by default."""


type Decorator[F] = t.Callable[[F], F]


def parametrized[T, F: t.Callable[..., t.Any]](
    argname: str, cases: dict[str, T]
) -> Decorator[F]:
    """More convenient test parametrization, using a dict to provide names for each case.

    ```python
    @parametrized("arg", {"foo": 1, "bar": 2})
    def test_something(arg: int): ...
    ```
    """
    return pytest.mark.parametrize(
        argname, [pytest.param(value, id=key) for key, value in cases.items()]
    )


def write_file(dest: str | pathlib.Path, *, source: pathlib.Path) -> pathlib.Path:
    """Copy the `source` contents into the `dest` file.

    Returns the `dest` path.
    """
    dest = pathlib.Path(dest)
    dest.write_bytes(source.read_bytes())
    return dest


class ExamplePackage(t.TypedDict, total=False):
    """Key information for an example package in a lockfile."""

    name: str
    version: str
    source_toml: str


def example_uv_lockfile(dest: pathlib.Path, *packages: ExamplePackage) -> pathlib.Path:
    """Create an example `uv.lock` file."""
    default_source_toml = '{ registry = "https://pypi.org/simple" }'

    lockfile = """\
version = 1
revision = 3
requires-python = ">=3.12"
"""
    for package in packages:
        lockfile += f"""\

[[package]]
name = "{package.get("name", "example")}"
version = "{package.get("version", "0.1.0")}"
source = {package.get("source_toml", default_source_toml)}
"""

    if not packages:
        lockfile += "package = []"

    dest.write_text(lockfile)
    return dest


def example_poetry_lockfile(
    dest: pathlib.Path,
    *packages: ExamplePackage,
) -> pathlib.Path:
    """Create an example `poetry.lock` file."""
    lockfile = ""
    for package in packages:
        lockfile += f"""\

[[package]]
name = "{package.get("name", "example")}"
version = "{package.get("version", "0.1.0")}"
    """
        if source_toml := package.get("source_toml"):
            lockfile += f"""\

[package.source]
{source_toml}
"""

    if not lockfile:
        lockfile = "package = []"

    dest.write_text(f"""\
{lockfile.strip()}

[metadata]
lock-version = "2.1"
python-versions = ">=3.12"
content-hash = "0000000000000000000000000000000000000000000000000000000000000000"
""")
    return dest
