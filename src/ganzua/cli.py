"""The ganzua command-line interface."""

import contextlib
import dataclasses
import enum
import pathlib
import shlex
import shutil
import subprocess
import tempfile
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
from ._filters import ConstraintFilter, LockfileFilter
from ._lockfile import lockfile_by_name
from ._markdown import MarkdownRenderer, md_from_requirements
from ._markdown_from_json_schema import md_from_schema
from ._utils import coalesce, error_context

app = App(
    name="ganzua",
    help="""\
Inspect Python dependency lockfiles (uv, Poetry, pylock.toml).

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
            case other:
                t.assert_never(other)


_OutputFormatOption: t.TypeAlias = t.Annotated[
    OutputFormat,
    clack.Option(help="Choose the output format, e.g. Markdown. [default: json]"),
]

_ExistingPath = click.Path(
    exists=True, path_type=pathlib.Path, file_okay=True, dir_okay=True
)
_OptionalExistingPathArgument = t.Annotated[
    pathlib.Path | None, clack.Argument(type=_ExistingPath)
]
_DeprecatedNameLockfileFilter = t.Annotated[
    LockfileFilter | None,
    clack.Option(help=None, deprecated="Use `--filter` instead of `--name`."),
]
_DeprecatedNameConstraintFilter = t.Annotated[
    ConstraintFilter | None,
    clack.Option(help=None, deprecated="Use `--filter` instead of `--name`."),
]
_GitOption = t.Annotated[
    bool,
    clack.Option(
        "--git/--no-git",
        help="Whether to interpret lockfile paths as gitrevisions. [default: enabled]",
    ),
]
_GitExecutableOption = t.Annotated[
    str,
    clack.Option(help="How to invoke Git. [default: git]", metavar="EXECUTABLE"),
]


DIFF_SCHEMA = pydantic.TypeAdapter(ganzua.Diff)
LOCKFILE_SCHEMA = pydantic.TypeAdapter(ganzua.Lockfile)
REQUIREMENTS_SCHEMA = pydantic.TypeAdapter(ganzua.Requirements)


@app.command()
def inspect(  # noqa: PLR0913  # too-many-arguments
    lockfile: t.Annotated[str | None, clack.Argument()] = None,
    filter: t.Annotated[
        LockfileFilter | None,
        clack.Option(help="Include/exclude packages to inspect. [default: show all]"),
    ] = None,
    name: _DeprecatedNameLockfileFilter = None,
    format: _OutputFormatOption = OutputFormat.JSON,
    git: _GitOption = True,
    git_executable: _GitExecutableOption = "git",
    md_links: t.Annotated[bool, clack.Option(help=None)] = False,
) -> None:
    """Inspect a lockfile.

    The `LOCKFILE` argument can be any of the following:

    * file: use that path as the lockfile (e.g. `uv.lock` or `poetry.lock`)
    * directory: look for a lockfile in that directory
    * gitrevision: a `<commit>:<path>` identifying a lockfile in the Git history

    If this argument is not specified,
    the one in the current working directory will be used.

    <!-- options -->

    *Changed in Ganzua NEXT:* renamed `--name` to `--filter`.
    """
    ctx = click.get_current_context()
    filter = coalesce(filter, name, default=LockfileFilter.DEFAULT)
    lockfile_data = _LockfileResolver(
        ctx=ctx,
        project_dir=pathlib.Path(),
        git_executable=git_executable if git else None,
    ).load_lockfile(lockfile, metavar="LOCKFILE")
    lockfile_data = filter.filtered_lockfile(lockfile_data)
    renderer = MarkdownRenderer(show_links=md_links)
    format.print(
        lockfile_data,
        adapter=LOCKFILE_SCHEMA,
        markdown=renderer.md_from_lockfile,
    )


@app.command()
def diff(  # noqa: PLR0913  # too-many-arguments
    old: t.Annotated[str, clack.Argument()],
    new: t.Annotated[str, clack.Argument()],
    filter: t.Annotated[
        LockfileFilter | None,
        clack.Option(help="Include/exclude packages to diff. [default: diff all]"),
    ] = None,
    name: _DeprecatedNameLockfileFilter = None,
    format: _OutputFormatOption = OutputFormat.JSON,
    git: _GitOption = True,
    git_executable: _GitExecutableOption = "git",
    md_links: t.Annotated[bool, clack.Option(help=None)] = False,
) -> None:
    """Compare two lockfiles.

    The `OLD` and `NEW` arguments can be any of the following:

    * file: use that path as the lockfile (e.g. `uv.lock` or `poetry.lock`)
    * directory: look for a lockfile in that directory
    * gitrevision: a `<commit>:<path>` identifying a lockfile in the Git history

    Here's an example of using the Git feature to show non-committed changes in a lockfile:

    ```bash
    ganzua diff HEAD:uv.lock uv.lock
    ```

    <!-- options -->

    *Changed in Ganzua NEXT:* renamed `--name` to `--filter`.
    """
    ctx = click.get_current_context()
    filter = coalesce(filter, name, default=LockfileFilter.DEFAULT)
    lockfile_resolver = _LockfileResolver(
        ctx=ctx,
        project_dir=pathlib.Path(),  # unused
        git_executable=git_executable if git else None,
    )
    diff = ganzua.diff(
        lockfile_by_name(
            filter.filtered_lockfile(
                (lockfile_resolver.load_lockfile(old, metavar="OLD"))
            )
        ),
        lockfile_by_name(
            filter.filtered_lockfile(
                (lockfile_resolver.load_lockfile(new, metavar="NEW"))
            )
        ),
    )
    renderer = MarkdownRenderer(show_links=md_links)
    format.print(
        diff,
        adapter=DIFF_SCHEMA,
        markdown=renderer.md_from_diff,
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


@dataclasses.dataclass(kw_only=True)
class _LockfileResolver:
    ctx: click.Context
    project_dir: pathlib.Path
    git_executable: str | None = None
    note: str | None = None

    def load_lockfile(
        self, lockfile: pathlib.Path | str | None, *, metavar: str
    ) -> ganzua.Lockfile:
        data = self._maybe_load_from_git(lockfile)
        if data is None:
            data = ganzua.lockfile_from(
                self._resolve_lockfile(lockfile, metavar=metavar)
            )
        return data

    def _maybe_load_from_git(
        self, revision: pathlib.Path | str | None
    ) -> ganzua.Lockfile | None:
        if not self.git_executable:
            return None
        if not isinstance(revision, str):
            return None
        if revision.startswith(("/", "./", "../")):
            return None
        if ":" not in revision:
            return None
        # TODO parse directly, without tempfile
        temp = self.ctx.with_resource(tempfile.NamedTemporaryFile())  # noqa: SIM115
        result = subprocess.run(
            [self.git_executable, "cat-file", "blob", revision],
            stdout=temp,
            check=False,
        )
        if result.returncode:
            msg = f"Could not read file from Git history: `{revision}`"
            msg += f"\nNote: Command `{shlex.join(result.args)}` exited with status {result.returncode}"
            self.ctx.fail(msg)
        return ganzua.lockfile_from(pathlib.Path(temp.name), name=revision)

    def _resolve_lockfile(
        self, lockfile: pathlib.Path | str | None, *, metavar: str
    ) -> pathlib.Path:

        if lockfile is None:
            return self._find_lockfile_in_dir(self.project_dir, metavar=metavar)

        lockfile = pathlib.Path(lockfile)
        if lockfile.is_dir():
            return self._find_lockfile_in_dir(lockfile, metavar=metavar)

        if not lockfile.exists():
            msg = f"{metavar}: Path `{lockfile}` does not exist."
            if self.note:
                msg += f"\nNote: {self.note}"
            self.ctx.fail(msg)

        return lockfile

    def _find_lockfile_in_dir(
        self, project_dir: pathlib.Path, *, metavar: str
    ) -> pathlib.Path:
        candidates = [
            project_dir / "uv.lock",
            project_dir / "poetry.lock",
            project_dir / "pylock.toml",
        ]
        match [f for f in candidates if f.exists()]:
            case [exactly_one]:
                return exactly_one
            case existing_lockfiles:
                msg = f"Could not infer `{metavar}` for `{project_dir}`."
                for f in existing_lockfiles:
                    msg += f"\nNote: Candidate lockfile: {shlex.quote(str(f))}"
                if self.note:
                    msg += f"\nNote: {self.note}"
                self.ctx.fail(msg)


@constraints.command("inspect")
def constraints_inspect(
    pyproject: _OptionalExistingPathArgument = None,
    filter: t.Annotated[
        ConstraintFilter | None,
        clack.Option(help="Include/exclude constraints to show. [default: show all]"),
    ] = None,
    name: _DeprecatedNameConstraintFilter = None,
    format: _OutputFormatOption = OutputFormat.JSON,
) -> None:
    """List all constraints in the `pyproject.toml` file.

    The `PYPROJECT` argument should point to a `pyproject.toml` file,
    or to a directory containing such a file.
    If this argument is not specified,
    the one in the current working directory will be used.

    <!-- options -->

    *Changed in Ganzua NEXT:* renamed `--name` to `--filter`.
    """
    ctx = click.get_current_context()
    filter = coalesce(filter, name, default=ConstraintFilter.DEFAULT)
    pyproject = _find_pyproject_toml(ctx, pyproject)

    with error_context(f"while parsing {pyproject}"):
        doc = toml.RefRoot.parse(pyproject.read_text())
    collector = ganzua.CollectRequirement([])
    ganzua.edit_pyproject(doc, FilteredEdit(collector, filter=filter))
    reqs = ganzua.Requirements(requirements=collector.reqs)
    format.print(reqs, adapter=REQUIREMENTS_SCHEMA, markdown=md_from_requirements)


@constraints.command("bump")
def constraints_bump(
    pyproject: _OptionalExistingPathArgument = None,
    lockfile: t.Annotated[
        str | None,
        clack.Option(
            metavar="PATH",
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
    filter: t.Annotated[
        ConstraintFilter | None,
        clack.Option(help="Include/exclude constraints to edit. [default: edit all]"),
    ] = None,
    name: _DeprecatedNameConstraintFilter = None,
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

    <!-- options -->

    *Changed in Ganzua NEXT:* renamed `--name` to `--filter`.
    """
    ctx = click.get_current_context()
    filter = coalesce(filter, name, default=ConstraintFilter.DEFAULT)
    warnings = _PlainWarnings()
    pyproject = _find_pyproject_toml(ctx, pyproject)
    locked = _LockfileResolver(ctx=ctx, project_dir=pyproject.parent).load_lockfile(
        lockfile, metavar="--lockfile"
    )

    if backup is not None:
        shutil.copy(pyproject, backup)

    edit: ganzua.EditRequirement = ganzua.UpdateRequirement(
        lockfile=lockfile_by_name(locked),
        warn_multiple_versions=warnings.warn_multiple_candidate_versions,
    )
    edit = FilteredEdit(edit, filter=filter)
    with _toml_edit_scope(pyproject) as doc:
        ganzua.edit_pyproject(doc, edit)


class ConstraintResetGoal(enum.Enum):
    """Intended result for `ganzua constraints reset` operations."""

    NONE = enum.auto()
    """Remove all constraints."""

    MINIMUM = enum.auto()
    """Set constraints constraints to the currently locked minimum, removing upper bounds."""


@constraints.command("reset")
def constraints_reset(  # noqa: PLR0913 # too-many-arguments
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
        str | None,
        clack.Option(
            metavar="PATH",
            help="""\
Where to load current versions from (for `--to=minimum`). Inferred if possible.
* file: use the path as the lockfile
* directory: use the lockfile in that directory
* default: use the lockfile in the `PYPROJECT` directory
""",
        ),
    ] = None,
    filter: t.Annotated[
        ConstraintFilter | None,
        clack.Option(help="Include/exclude constraints to edit. [default: edit all]"),
    ] = None,
    name: _DeprecatedNameConstraintFilter = None,
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

    <!-- options -->

    *Changed in Ganzua NEXT:* renamed `--name` to `--filter`.
    """
    ctx = click.get_current_context()
    filter = coalesce(filter, name, default=ConstraintFilter.DEFAULT)
    warnings = _PlainWarnings()
    pyproject = _find_pyproject_toml(ctx, pyproject)
    lockfile_resolver = _LockfileResolver(
        ctx=ctx,
        project_dir=pyproject.parent,
        note="Using `--to=minimum` requires a `--lockfile`.",
    )

    edit: ganzua.EditRequirement
    match to:
        case ConstraintResetGoal.NONE:
            edit = ganzua.UnconstrainRequirement()
        case ConstraintResetGoal.MINIMUM:
            locked = lockfile_resolver.load_lockfile(lockfile, metavar="--lockfile")
            edit = ganzua.SetMinimumRequirement(
                lockfile_by_name(locked),
                warnings.warn_multiple_candidate_versions,
            )
        case other:
            t.assert_never(other)

    edit = FilteredEdit(edit, filter=filter)

    if backup is not None:
        shutil.copy(pyproject, backup)

    with _toml_edit_scope(pyproject) as doc:
        ganzua.edit_pyproject(doc, edit)


@contextlib.contextmanager
def _toml_edit_scope(path: pathlib.Path) -> t.Generator[toml.Ref, None, None]:
    """Load the TOML file and write it back afterwards."""
    with error_context(f"while parsing {path}"):
        old_contents = path.read_text()
        doc = toml.RefRoot.parse(old_contents)

    yield doc

    new_contents = doc.dumps()
    if new_contents != old_contents:
        path.write_text(new_contents)


@app.command()
def schema(
    command: t.Annotated[
        t.Literal["inspect", "diff", "constraints-inspect"], clack.Argument()
    ],
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
        case other:
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
