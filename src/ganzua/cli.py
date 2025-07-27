"""The ganzua command-line interface."""

import contextlib
import enum
import functools
import pathlib
import typing as t

import click
import pydantic
import rich
import tomlkit

import ganzua

from ._cli_help import App
from ._utils import error_context

app = App(
    name="ganzua",
    help="""\
Inspect Python dependency lockfiles (uv and Poetry).

<!-- options -->

Ganzua is licensed under the Apache-2.0 license.
""",
)


type _Jsonish = t.Mapping[str, t.Any]


def _with_print_json[**P](command: t.Callable[P, _Jsonish]) -> t.Callable[P, None]:
    @functools.wraps(command)
    def command_with_json_output(*args: P.args, **kwargs: P.kwargs) -> None:
        rich.print_json(data=command(*args, **kwargs))

    return command_with_json_output


class _CommmandWithSchema(enum.StrEnum):
    schema: pydantic.TypeAdapter[t.Any]

    inspect = "inspect", ganzua.LOCKFILE_SCHEMA
    diff = "diff", ganzua.DIFF_SCHEMA

    def __new__(cls, discriminator: str, schema: pydantic.TypeAdapter[t.Any]) -> t.Self:
        # Overriding __new__() of an enum is a bit tricky,
        # see <https://docs.python.org/3/howto/enum.html#when-to-use-new-vs-init>.
        # We cannot use super() and must invoke the underlying type directly.
        # We must assign the special `_value_` field.
        self = str.__new__(cls, discriminator)
        self._value_ = discriminator
        self.schema = schema
        return self


_ExistingFilePath = click.Path(
    exists=True, path_type=pathlib.Path, file_okay=True, dir_okay=False
)


@app.command()
@click.argument("lockfile", type=_ExistingFilePath)
@_with_print_json
def inspect(lockfile: pathlib.Path) -> _Jsonish:
    """Inspect a lockfile."""
    return ganzua.lockfile_from(lockfile)


@app.command()
@click.argument("old", type=_ExistingFilePath)
@click.argument("new", type=_ExistingFilePath)
@_with_print_json
def diff(old: pathlib.Path, new: pathlib.Path) -> _Jsonish:
    """Compare two lockfiles."""
    return ganzua.diff(
        ganzua.lockfile_from(old),
        ganzua.lockfile_from(new),
    )


@app.command()
@click.argument("lockfile", type=_ExistingFilePath)
@click.argument("pyproject", type=_ExistingFilePath)
def update_constraints(lockfile: pathlib.Path, pyproject: pathlib.Path) -> None:
    """Update pyproject.toml dependency constraints to match the lockfile.

    Of course, the lockfile should always be a valid solution for the constraints.
    But this tool will increment the constraints to match the current locked versions.
    Often, constraints are somewhat relaxed.
    This tool will try to be as granular as the original constraint.
    For example, given the old constraint `foo>=3.5` and the new version `4.7.2`,
    the constraint would be updated to `foo>=4.7`.
    """
    locked = ganzua.lockfile_from(lockfile)
    with _toml_edit_scope(pyproject) as doc:
        ganzua.update_pyproject(doc, locked)


@app.command()
@click.argument("pyproject", type=_ExistingFilePath)
def remove_constraints(pyproject: pathlib.Path) -> None:
    """Remove any dependency version constraints from the `pyproject.toml`.

    This can be useful for allowing uv/Poetry to update to the most recent versions,
    ignoring the previous constraints. Approximate recipe:

    ```bash
    cp pyproject.toml pyproject.toml.bak
    ganzua remove-constraints pyproject.toml
    uv lock --upgrade  # perform the upgrade
    mv pyproject.toml.bak pyproject.toml  # restore old constraints
    ganzua update-constraints uv.lock pyproject.toml
    uv lock
    ```
    """
    with _toml_edit_scope(pyproject) as doc:
        ganzua.unconstrain_pyproject(doc)


@contextlib.contextmanager
def _toml_edit_scope(path: pathlib.Path) -> t.Iterator[tomlkit.TOMLDocument]:
    """Load the TOML file and write it back afterwards."""
    with error_context(f"while parsing {path}"):
        old_contents = path.read_text()
        doc = tomlkit.parse(old_contents)

    yield doc

    new_contents = doc.as_string()
    if new_contents != old_contents:
        path.write_text(new_contents)


@app.command()
@click.argument("command", type=click.Choice(_CommmandWithSchema))
@_with_print_json
def schema(command: _CommmandWithSchema) -> _Jsonish:
    """Show the JSON schema for the output of the given command."""
    return command.schema.json_schema()
