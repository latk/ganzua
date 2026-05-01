"""The ganzua command-line interface."""

import contextlib
import enum
import pathlib
import shlex
import shutil
import typing as t

import click
import pydantic
import rich
from packaging.version import Version

import ganzua

from . import _clack as clack
from . import _toml as toml
from ._cli_help import App
from ._edit_requirement import FilteredEdit
from ._filters import Filter, filter_lockfile
from ._lockfile import lockfile_by_name
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

    def print[T](
        self,
        data: T,
        *,
        adapter: pydantic.TypeAdapter[T] | t.Callable[[T], pydantic.JsonValue],
        markdown: t.Callable[[T], str],
    ) -> None:
        """Print the given data with this output format."""
        match self:
            case OutputFormat.JSON:
                if isinstance(adapter, pydantic.TypeAdapter):
                    json_data = adapter.dump_python(data, mode="json")
                else:
                    json_data = adapter(data)
                rich.print_json(data=json_data)
            case OutputFormat.MARKDOWN:
                click.echo(markdown(data))
            case other:  # pragma: no cover
                t.assert_never(other)


_OutputFormatOption: t.TypeAlias = t.Annotated[
    OutputFormat,
    clack.Option(help="Choose the output format, e.g. Markdown. [default: json]"),
]

_ExistingPath = click.Path(
    exists=True, path_type=pathlib.Path, file_okay=True, dir_okay=True
)
_ExistingPathArgument = t.Annotated[pathlib.Path, clack.Argument(type=_ExistingPath)]
_OptionalExistingPathArgument = t.Annotated[
    pathlib.Path | None, clack.Argument(type=_ExistingPath)
]


DIFF_SCHEMA = pydantic.TypeAdapter(ganzua.Diff)
LOCKFILE_SCHEMA = pydantic.TypeAdapter(ganzua.Lockfile)
REQUIREMENTS_SCHEMA = pydantic.TypeAdapter(ganzua.Requirements)


@app.command()
def inspect(
    lockfile: _OptionalExistingPathArgument = None,
    name: t.Annotated[
        Filter,
        clack.Option(
            help="Include/exclude packages to inspect by name. [default: show all]"
        ),
    ] = Filter.DEFAULT,
    format: _OutputFormatOption = OutputFormat.JSON,
) -> None:
    """Inspect a lockfile.

    The `LOCKFILE` should point to an `uv.lock` or `poetry.lock` file,
    or to a directory containing such a file.
    If this argument is not specified,
    the one in the current working directory will be used.
    """
    ctx = click.get_current_context()
    lockfile = _find_lockfile(
        ctx,
        lockfile,
        project_dir=pathlib.Path(),
        err_msg=lambda project_dir: f"Could not infer `LOCKFILE` for `{project_dir}`.",
    )

    lockfile_data = ganzua.lockfile_from(lockfile)
    lockfile_data = filter_lockfile(lockfile_data, name_filter=name)
    format.print(lockfile_data, adapter=LOCKFILE_SCHEMA, markdown=md_from_lockfile)


@app.command()
def diff(
    old: _ExistingPathArgument,
    new: _ExistingPathArgument,
    name: t.Annotated[
        Filter,
        clack.Option(
            help="Include/exclude packages to diff by name. [default: diff all]"
        ),
    ] = Filter.DEFAULT,
    format: _OutputFormatOption = OutputFormat.JSON,
) -> None:
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
    ctx = click.get_current_context()
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
    diff = ganzua.diff(
        lockfile_by_name(filter_lockfile(ganzua.lockfile_from(old), name_filter=name)),
        lockfile_by_name(filter_lockfile(ganzua.lockfile_from(new), name_filter=name)),
    )
    format.print(diff, adapter=DIFF_SCHEMA, markdown=md_from_diff)


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
def constraints_inspect(
    pyproject: _OptionalExistingPathArgument = None,
    name: t.Annotated[
        Filter,
        clack.Option(
            help="Include/exclude constraints to show by package name. [default: show all]"
        ),
    ] = Filter.DEFAULT,
    format: _OutputFormatOption = OutputFormat.JSON,
) -> None:
    """List all constraints in the `pyproject.toml` file.

    The `PYPROJECT` argument should point to a `pyproject.toml` file,
    or to a directory containing such a file.
    If this argument is not specified,
    the one in the current working directory will be used.
    """
    ctx = click.get_current_context()
    pyproject = _find_pyproject_toml(ctx, pyproject)

    with error_context(f"while parsing {pyproject}"):
        doc = toml.RefRoot.parse(pyproject.read_text())
    collector = ganzua.CollectRequirement([])
    ganzua.edit_pyproject(doc, FilteredEdit(collector, name=name))
    reqs = ganzua.Requirements(requirements=collector.reqs)
    format.print(reqs, adapter=REQUIREMENTS_SCHEMA, markdown=md_from_requirements)


@constraints.command("bump")
def constraints_bump(
    pyproject: _OptionalExistingPathArgument = None,
    lockfile: t.Annotated[
        pathlib.Path | None,
        clack.Option(
            type=_ExistingPath,
            help="""\
Where to load versions from. Inferred if possible.
* file: use the path as the lockfile
* directory: use the lockfile in that directory
* default: use the lockfile in the `PYPROJECT` directory
""",
        ),
    ] = None,
    backup: t.Annotated[
        pathlib.Path | None, clack.Option(help="Store a backup in this file.")
    ] = None,
    name: t.Annotated[
        Filter,
        clack.Option(
            help="Include/exclude constraints to edit by package name. [default: edit all]"
        ),
    ] = Filter.DEFAULT,
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
    ctx = click.get_current_context()
    warnings = _PlainWarnings()
    pyproject = _find_pyproject_toml(ctx, pyproject)
    lockfile = _find_lockfile(
        ctx,
        lockfile,
        project_dir=pyproject.parent,
        err_msg=lambda project_dir: (
            f"Could not infer `--lockfile` for `{project_dir}`."
        ),
    )

    if backup is not None:
        shutil.copy(pyproject, backup)

    locked = ganzua.lockfile_from(lockfile)
    edit: ganzua.EditRequirement = ganzua.UpdateRequirement(
        lockfile=lockfile_by_name(locked),
        warn_multiple_versions=warnings.warn_multiple_candidate_versions,
    )
    edit = FilteredEdit(edit, name=name)
    with _toml_edit_scope(pyproject) as doc:
        ganzua.edit_pyproject(doc, edit)


class ConstraintResetGoal(enum.Enum):
    """Intended result for `ganzua constraints reset` operations."""

    NONE = enum.auto()
    """Remove all constraints."""

    MINIMUM = enum.auto()
    """Set constraints constraints to the currently locked minimum, removing upper bounds."""


@constraints.command("reset")
def constraints_reset(  # too-many-arguments
    pyproject: _OptionalExistingPathArgument = None,
    *,
    backup: t.Annotated[
        pathlib.Path | None, clack.Option(help="Store a backup in this file.")
    ] = None,
    to: t.Annotated[
        ConstraintResetGoal,
        clack.Option(
            help="""\
How to reset constraints.
* `none` (default): remove all constraints
* `minimum`: set constraints to the currently locked minimum, removing upper bounds
""",
        ),
    ] = ConstraintResetGoal.NONE,
    lockfile: t.Annotated[
        pathlib.Path | None,
        clack.Option(
            type=_ExistingPath,
            help="""\
Where to load current versions from (for `--to=minimum`). Inferred if possible.
* file: use the path as the lockfile
* directory: use the lockfile in that directory
* default: use the lockfile in the `PYPROJECT` directory
""",
        ),
    ] = None,
    name: t.Annotated[
        Filter,
        clack.Option(
            help="Include/exclude constraints to edit by package name. [default: edit all]"
        ),
    ] = Filter.DEFAULT,
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
    ctx = click.get_current_context()
    warnings = _PlainWarnings()
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
                err_msg=lambda project_dir: (
                    f"Could not infer `--lockfile` for `{project_dir}`."
                ),
                note="Using `--to=minimum` requires a `--lockfile`.",
            )
            edit = ganzua.SetMinimumRequirement(
                lockfile_by_name(ganzua.lockfile_from(lockfile)),
                warnings.warn_multiple_candidate_versions,
            )
        case other:  # pragma: no cover
            t.assert_never(other)

    edit = FilteredEdit(edit, name=name)

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
def schema(
    command: t.Annotated[SchemaName, clack.Argument()],
    format: _OutputFormatOption = OutputFormat.JSON,
) -> None:
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
    schema = adapter.json_schema(mode="serialization")
    format.print(schema, adapter=lambda s: s, markdown=md_from_schema)


class _PlainWarnings:
    def __init__(self) -> None:
        self.seen = set[str]()

    def warn(self, msg: str) -> None:
        if msg in self.seen:
            return
        click.echo(f"ganzua: {msg}", err=True)
        self.seen.add(msg)

    def warn_multiple_candidate_versions(
        self, package: str, versions: tuple[Version, ...]
    ) -> None:
        versions_str = ", ".join(str(v) for v in versions)
        msg = f"package `{package}` has multiple candidate versions: {versions_str}"
        self.warn(msg)
