"""The lockinator command-line interface."""

import enum
import functools
import pathlib
import typing as t

import pydantic
import rich
import tomlkit
import typer

import lockinator
from lockinator._utils import error_context

app = typer.Typer()

type _Jsonish = t.Mapping[str, t.Any]


def _with_print_json[**P](command: t.Callable[P, _Jsonish]) -> t.Callable[P, None]:
    @functools.wraps(command)
    def command_with_json_output(*args: P.args, **kwargs: P.kwargs) -> None:
        rich.print_json(data=command(*args, **kwargs))

    return command_with_json_output


class _CommmandWithSchema(enum.StrEnum):
    schema: pydantic.TypeAdapter[t.Any]

    inspect = "inspect", lockinator.LOCKFILE_SCHEMA
    diff = "diff", lockinator.DIFF_SCHEMA

    def __new__(cls, discriminator: str, schema: pydantic.TypeAdapter[t.Any]) -> t.Self:
        # Overriding __new__() of an enum is a bit tricky,
        # see <https://docs.python.org/3/howto/enum.html#when-to-use-new-vs-init>.
        # We cannot use super() and must invoke the underlying type directly.
        # We must assign the special `_value_` field.
        self = str.__new__(cls, discriminator)
        self._value_ = discriminator
        self.schema = schema
        return self


@app.command()
@_with_print_json
def inspect(lockfile: pathlib.Path) -> _Jsonish:
    """Inspect a lockfile."""
    return lockinator.lockfile_from(lockfile)


@app.command()
@_with_print_json
def diff(old: pathlib.Path, new: pathlib.Path) -> _Jsonish:
    """Compare two lockfiles."""
    return lockinator.diff(
        lockinator.lockfile_from(old),
        lockinator.lockfile_from(new),
    )


@app.command()
def update_constraints(lockfile: pathlib.Path, pyproject: pathlib.Path) -> None:
    """Update pyproject.toml dependency constraints to match the lockfile.

    Of course, the lockfile should always be a valid solution for the constraints.
    But this tool will increment the constraints to match the current locked version.s
    Often, constraints are somewhat relaxed.
    This tool will try to be as granular as the original constraint.
    For example, given the old constraint `foo>=3.5` and the new version `4.7.2`,
    the constraint would be updated to `foo>=4.7`.

    Currently only supports PEP-621 pyproject.toml files, but no legacy Poetry.
    """
    locked = lockinator.lockfile_from(lockfile)
    with error_context(f"while parsing {pyproject}"):
        old_contents = pyproject.read_text()
        doc = tomlkit.parse(old_contents)

    lockinator.update_pyproject(doc, locked)

    new_contents = doc.as_string()
    pyproject.write_text(new_contents)


@app.command()
@_with_print_json
def schema(command: _CommmandWithSchema) -> _Jsonish:
    """Show the JSON schema for the output of the given command."""
    return command.schema.json_schema()
