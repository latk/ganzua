"""The ganzua command-line interface."""

import contextlib
import enum
import functools
import pathlib
import shlex
import shutil
import typing as t
from dataclasses import dataclass

import click
import pydantic
import rich

import ganzua

from . import _toml as toml
from ._cli_help import App
from ._markdown import md_from_diff, md_from_lockfile, md_from_requirements
from ._markdown_from_json_schema import md_from_schema
from ._utils import error_context

app = App(
    name="ganzua",
    help="""\
Inspect Python dependency lockfiles (uv and Poetry).

<!-- options -->

For more information, see the Ganzua website at "<https://github.com/latk/ganzua>".

Ganzua is licensed under the Apache-2.0 license.
""",
)


type _Jsonish = t.Mapping[str, t.Any]


class OutputFormat(enum.Enum):
    """Different output formats available for structured data."""

    JSON = enum.auto()
    MARKDOWN = enum.auto()


@dataclass
class _with_print_json[R]:  # noqa: N801  # invalid-name
    """Decorator for pretty-printing returned data from a Click command."""

    adapter: pydantic.TypeAdapter[R] | t.Callable[[R], pydantic.JsonValue]
    markdown: t.Callable[[R], str]

    def __call__[**P](
        self, command: t.Callable[P, R]
    ) -> t.Callable[t.Concatenate[OutputFormat, P], None]:
        @functools.wraps(command)
        @click.option(
            "--format",
            type=click.Choice(OutputFormat, case_sensitive=False),
            default=OutputFormat.JSON,
            show_default=True,
            help="Choose the output format, e.g. Markdown. [default: json]",
        )
        def command_with_json_output(
            format: OutputFormat, *args: P.args, **kwargs: P.kwargs
        ) -> None:
            data = command(*args, **kwargs)
            match format:
                case OutputFormat.JSON:
                    if isinstance(self.adapter, pydantic.TypeAdapter):
                        json_data = self.adapter.dump_python(data, mode="json")
                    else:
                        json_data = self.adapter(data)
                    rich.print_json(data=json_data)
                case OutputFormat.MARKDOWN:
                    click.echo(self.markdown(data))
                case other:  # pragma: no cover
                    t.assert_never(other)

        return command_with_json_output


_ExistingPath = click.Path(
    exists=True, path_type=pathlib.Path, file_okay=True, dir_okay=True
)


DIFF_SCHEMA = pydantic.TypeAdapter(ganzua.Diff)
LOCKFILE_SCHEMA = pydantic.TypeAdapter(ganzua.Lockfile)
REQUIREMENTS_SCHEMA = pydantic.TypeAdapter(ganzua.Requirements)


@app.command()
@click.argument("lockfile", type=_ExistingPath, required=False)
@_with_print_json(LOCKFILE_SCHEMA, md_from_lockfile)
@click.pass_context
def inspect(ctx: click.Context, lockfile: pathlib.Path | None) -> ganzua.Lockfile:
    """Inspect a lockfile.

    The `LOCKFILE` should point to an `uv.lock` or `poetry.lock` file,
    or to a directory containing such a file.
    If this argument is not specified,
    the one in the current working directory will be used.
    """
    lockfile = _find_lockfile(
        ctx,
        lockfile,
        project_dir=pathlib.Path(),
        err_msg=lambda project_dir: f"Could not infer `LOCKFILE` for `{project_dir}`.",
    )
    return ganzua.lockfile_from(lockfile)


@app.command()
@click.argument("old", type=_ExistingPath)
@click.argument("new", type=_ExistingPath)
@_with_print_json(DIFF_SCHEMA, md_from_diff)
@click.pass_context
def diff(ctx: click.Context, old: pathlib.Path, new: pathlib.Path) -> ganzua.Diff:
    """Compare two lockfiles.

    The `OLD` and `NEW` arguments must each point to an `uv.lock` or `poetry.lock` file,
    or to a directory containing such a file.

    There is no direct support for comparing a file across Git commits,
    but it's possible to retrieve other versions via [`git show`][git-show].
    Here is an example using a Bash redirect to show non-committed changes in a lockfile:

    ```bash
    ganzua diff <(git show HEAD:uv.lock) uv.lock
    ```

    [git-show]: https://git-scm.com/docs/git-show
    """
    old = _find_lockfile(
        ctx,
        old,
        project_dir=pathlib.Path(),  # unused
        err_msg=lambda project_dir: f"Could not infer `OLD` for `{project_dir}`.",
    )
    new = _find_lockfile(
        ctx,
        new,
        project_dir=pathlib.Path(),  # unused
        err_msg=lambda project_dir: f"Could not infer `NEW` for `{project_dir}`.",
    )
    return ganzua.diff(
        ganzua.lockfile_from(old),
        ganzua.lockfile_from(new),
    )


@app.group()
def constraints() -> None:
    """Work with `pyproject.toml` constraints."""


def _find_pyproject_toml(
    ctx: click.Context, pyproject: pathlib.Path | None
) -> pathlib.Path:
    if pyproject is None:
        project_dir = pathlib.Path()
    elif pyproject.is_dir():
        project_dir = pyproject
    else:
        return pyproject

    pyproject = project_dir / "pyproject.toml"
    if not (pyproject.exists() and pyproject.is_file()):
        ctx.fail("Did not find default `pyproject.toml`.")
    return pyproject


def _find_lockfile(
    ctx: click.Context,
    lockfile: pathlib.Path | None,
    *,
    project_dir: pathlib.Path,
    err_msg: t.Callable[[pathlib.Path], str],
    note: str | None = None,
) -> pathlib.Path:
    if lockfile is None:
        pass
    elif lockfile.is_dir():
        project_dir = lockfile
    else:
        return lockfile

    candidates = [
        project_dir / "uv.lock",
        project_dir / "poetry.lock",
    ]
    match [f for f in candidates if f.exists()]:
        case [exactly_one]:
            return exactly_one
        case existing_lockfiles:
            msg = err_msg(project_dir)
            for f in existing_lockfiles:
                msg += f"\nNote: Candidate lockfile: {shlex.quote(str(f))}"
            if note:
                msg += f"\nNote: {note}"
            ctx.fail(msg)


@constraints.command("inspect")
@click.argument("pyproject", type=_ExistingPath, required=False)
@_with_print_json(REQUIREMENTS_SCHEMA, md_from_requirements)
@click.pass_context
def constraints_inspect(
    ctx: click.Context, pyproject: pathlib.Path | None
) -> ganzua.Requirements:
    """List all constraints in the `pyproject.toml` file.

    The `PYPROJECT` argument should point to a `pyproject.toml` file,
    or to a directory containing such a file.
    If this argument is not specified,
    the one in the current working directory will be used.
    """
    pyproject = _find_pyproject_toml(ctx, pyproject)

    with error_context(f"while parsing {pyproject}"):
        doc = toml.RefRoot.parse(pyproject.read_text())
    collector = ganzua.CollectRequirement([])
    ganzua.edit_pyproject(doc, collector)
    return ganzua.Requirements(requirements=collector.reqs)


@constraints.command("bump")
@click.argument("pyproject", type=_ExistingPath, required=False)
@click.option(
    "--lockfile",
    type=_ExistingPath,
    required=False,
    help="""\
Where to load versions from. Inferred if possible.
* file: use the path as the lockfile
* directory: use the lockfile in that directory
* default: use the lockfile in the `PYPROJECT` directory
""",
)
@click.option("--backup", type=click.Path(), help="Store a backup in this file.")
@click.pass_context
def constraints_bump(
    ctx: click.Context,
    pyproject: pathlib.Path | None,
    lockfile: pathlib.Path | None,
    backup: pathlib.Path | None,
) -> None:
    """Update `pyproject.toml` dependency constraints to match the lockfile.

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
    """
    pyproject = _find_pyproject_toml(ctx, pyproject)
    lockfile = _find_lockfile(
        ctx,
        lockfile,
        project_dir=pyproject.parent,
        err_msg=lambda project_dir: f"Could not infer `--lockfile` for `{project_dir}`.",
    )

    if backup is not None:
        shutil.copy(pyproject, backup)

    locked = ganzua.lockfile_from(lockfile)
    with _toml_edit_scope(pyproject) as doc:
        ganzua.edit_pyproject(doc, ganzua.UpdateRequirement(locked))


class ConstraintResetGoal(enum.Enum):
    """Intended result for `ganzua constraints reset` operations."""

    NONE = enum.auto()
    """Remove all constraints."""

    MINIMUM = enum.auto()
    """Set constraints constraints to the currently locked minimum, removing upper bounds."""


@constraints.command("reset")
@click.argument("pyproject", type=_ExistingPath, required=False)
@click.option("--backup", type=click.Path(), help="Store a backup in this file.")
@click.option(
    "--to",
    type=click.Choice(ConstraintResetGoal, case_sensitive=False),
    default=ConstraintResetGoal.NONE,
    help="""\
How to reset constraints.
* `none` (default): remove all constraints
* `minimum`: set constraints to the currently locked minimum, removing upper bounds
""",
)
@click.option(
    "--lockfile",
    type=_ExistingPath,
    required=False,
    help="""\
Where to load current versions from (for `--to=minimum`). Inferred if possible.
* file: use the path as the lockfile
* directory: use the lockfile in that directory
* default: use the lockfile in the `PYPROJECT` directory
""",
)
@click.pass_context
def constraints_reset(
    ctx: click.Context,
    pyproject: pathlib.Path | None,
    *,
    backup: pathlib.Path | None,
    lockfile: pathlib.Path | None,
    to: ConstraintResetGoal,
) -> None:
    """Remove or relax any dependency version constraints from the `pyproject.toml`.

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
    """
    pyproject = _find_pyproject_toml(ctx, pyproject)

    edit: ganzua.EditRequirement
    match to:
        case ConstraintResetGoal.NONE:
            edit = ganzua.UnconstrainRequirement()
        case ConstraintResetGoal.MINIMUM:
            lockfile = _find_lockfile(
                ctx,
                lockfile,
                project_dir=pyproject.parent,
                err_msg=lambda project_dir: f"Could not infer `--lockfile` for `{project_dir}`.",
                note="Using `--to=minimum` requires a `--lockfile`.",
            )
            edit = ganzua.SetMinimumRequirement(ganzua.lockfile_from(lockfile))
        case other:  # pragma: no cover
            t.assert_never(other)

    if backup is not None:
        shutil.copy(pyproject, backup)

    with _toml_edit_scope(pyproject) as doc:
        ganzua.edit_pyproject(doc, edit)


@contextlib.contextmanager
def _toml_edit_scope(path: pathlib.Path) -> t.Iterator[toml.Ref]:
    """Load the TOML file and write it back afterwards."""
    with error_context(f"while parsing {path}"):
        old_contents = path.read_text()
        doc = toml.RefRoot.parse(old_contents)

    yield doc

    new_contents = doc.dumps()
    if new_contents != old_contents:
        path.write_text(new_contents)


SchemaName = t.Literal["inspect", "diff", "constraints-inspect"]


@app.command()
@click.argument("command", type=click.Choice(t.get_args(SchemaName)))
@_with_print_json(adapter=lambda schema: schema, markdown=md_from_schema)
def schema(command: SchemaName) -> pydantic.JsonValue:
    """Show the JSON schema for the output of the given command."""
    adapter: pydantic.TypeAdapter[t.Any]
    match command:
        case "inspect":
            adapter = LOCKFILE_SCHEMA
        case "diff":
            adapter = DIFF_SCHEMA
        case "constraints-inspect":
            adapter = REQUIREMENTS_SCHEMA
        case other:  # pragma: no cover
            t.assert_never(other)
    return adapter.json_schema(mode="serialization")
