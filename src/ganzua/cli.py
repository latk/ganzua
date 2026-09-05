"""The ganzua command-line interface."""

import contextlib
import dataclasses
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
from ._filters import ConstraintFilter, LockfileFilter
from ._git import Git
from ._lockfile import lockfile_by_name, parse_lockfile
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


@dataclasses.dataclass
class _LockfileFilterOptions:
    filter: t.Annotated[
        LockfileFilter | None,
        clack.Option(help="Include/exclude packages. [default: use all]"),
    ] = None
    name: t.Annotated[
        LockfileFilter | None,
        clack.Option(help=None, deprecated="Use `--filter` instead of `--name`."),
    ] = None

    def filtered_lockfile(self, lockfile: ganzua.Lockfile) -> ganzua.Lockfile:
        filter = coalesce(self.filter, self.name, default=LockfileFilter.DEFAULT)
        return filter.filtered_lockfile(lockfile)


@dataclasses.dataclass
class _ConstraintFilterOptions:
    filter: t.Annotated[
        ConstraintFilter | None,
        clack.Option(
            help="Include/exclude constraints to operate on. [default: use all]"
        ),
    ] = None
    name: t.Annotated[
        ConstraintFilter | None,
        clack.Option(help=None, deprecated="Use `--filter` instead of `--name`."),
    ] = None

    def get(self) -> ConstraintFilter:
        return coalesce(self.filter, self.name, default=ConstraintFilter.DEFAULT)


@dataclasses.dataclass
class _GitOptions:
    git: t.Annotated[
        bool,
        clack.Option(
            "--git/--no-git",
            help="Whether to interpret lockfile paths as gitrevisions. [default: enabled]",
        ),
    ] = True
    git_executable: t.Annotated[
        str,
        clack.Option(help="How to invoke Git. [default: git]", metavar="EXECUTABLE"),
    ] = "git"

    def get(self) -> Git | None:
        if not self.git:
            return None
        return Git(self.git_executable)


@dataclasses.dataclass
class _LockfileOutputOptions:
    format: _OutputFormatOption = OutputFormat.JSON
    md_links: t.Annotated[bool, clack.Option(help=None)] = False

    def print_lockfile(self, lockfile: ganzua.Lockfile) -> None:
        renderer = MarkdownRenderer(show_links=self.md_links)
        self.format.print(
            lockfile, adapter=LOCKFILE_SCHEMA, markdown=renderer.md_from_lockfile
        )

    def print_diff(self, diff: ganzua.Diff) -> None:
        renderer = MarkdownRenderer(show_links=self.md_links)
        self.format.print(diff, adapter=DIFF_SCHEMA, markdown=renderer.md_from_diff)


DIFF_SCHEMA = pydantic.TypeAdapter(ganzua.Diff)
LOCKFILE_SCHEMA = pydantic.TypeAdapter(ganzua.Lockfile)
REQUIREMENTS_SCHEMA = pydantic.TypeAdapter(ganzua.Requirements)


@app.command()
def inspect(
    *,
    lockfile: t.Annotated[str | None, clack.Argument()] = None,
    filter: _LockfileFilterOptions,
    output: _LockfileOutputOptions,
    git_options: _GitOptions,
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
    data = _DataLayer(git=git_options.get())
    lockfile_data = data.load_lockfile(
        lockfile, metavar="LOCKFILE", project_dir=pathlib.Path()
    )
    lockfile_data = filter.filtered_lockfile(lockfile_data)
    output.print_lockfile(lockfile_data)


@app.command()
def diff(
    *,
    old: t.Annotated[str, clack.Argument()],
    new: t.Annotated[str, clack.Argument()],
    filter: _LockfileFilterOptions,
    output: _LockfileOutputOptions,
    git_options: _GitOptions,
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
    data = _DataLayer(git=git_options.get())
    project_dir = pathlib.Path()  # effectively unused
    diff = ganzua.diff(
        lockfile_by_name(
            filter.filtered_lockfile(
                (data.load_lockfile(old, metavar="OLD", project_dir=project_dir))
            )
        ),
        lockfile_by_name(
            filter.filtered_lockfile(
                (data.load_lockfile(new, metavar="NEW", project_dir=project_dir))
            )
        ),
    )
    output.print_diff(diff)


@app.group()
def constraints() -> None:
    """Work with `pyproject.toml` constraints."""


@constraints.command("inspect")
def constraints_inspect(
    *,
    pyproject: _OptionalExistingPathArgument = None,
    filter: _ConstraintFilterOptions,
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
    data = _DataLayer(git=None)
    pyproject = data.find_pyproject_toml(pyproject)

    with error_context(f"while parsing {pyproject}"):
        doc = toml.RefRoot.parse(pyproject.read_text())
    collector = ganzua.CollectRequirement([])
    ganzua.edit_pyproject(doc, FilteredEdit(collector, filter=filter.get()))
    reqs = ganzua.Requirements(requirements=collector.reqs)
    format.print(reqs, adapter=REQUIREMENTS_SCHEMA, markdown=md_from_requirements)


@constraints.command("bump")
def constraints_bump(
    *,
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
    filter: _ConstraintFilterOptions,
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
    warnings = _PlainWarnings()
    data = _DataLayer(git=None)
    pyproject = data.find_pyproject_toml(pyproject)
    locked = data.load_lockfile(
        lockfile, metavar="--lockfile", project_dir=pyproject.parent
    )

    if backup is not None:
        shutil.copy(pyproject, backup)

    edit: ganzua.EditRequirement = ganzua.UpdateRequirement(
        lockfile=lockfile_by_name(locked),
        warn_multiple_versions=warnings.warn_multiple_candidate_versions,
    )
    edit = FilteredEdit(edit, filter=filter.get())
    with data.edit_toml(pyproject, metavar="PYPROJECT") as doc:
        ganzua.edit_pyproject(doc, edit)


class ConstraintResetGoal(enum.Enum):
    """Intended result for `ganzua constraints reset` operations."""

    NONE = enum.auto()
    """Remove all constraints."""

    MINIMUM = enum.auto()
    """Set constraints constraints to the currently locked minimum, removing upper bounds."""


@constraints.command("reset")
def constraints_reset(
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
    filter: _ConstraintFilterOptions,
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
    warnings = _PlainWarnings()
    data = _DataLayer(git=None)
    pyproject = data.find_pyproject_toml(pyproject)

    edit: ganzua.EditRequirement
    match to:
        case ConstraintResetGoal.NONE:
            edit = ganzua.UnconstrainRequirement()
        case ConstraintResetGoal.MINIMUM:
            with error_context("Using `--to=minimum` requires a `--lockfile`."):
                locked = data.load_lockfile(
                    lockfile, metavar="--lockfile", project_dir=pyproject.parent
                )
            edit = ganzua.SetMinimumRequirement(
                lockfile_by_name(locked),
                warnings.warn_multiple_candidate_versions,
            )
        case other:
            t.assert_never(other)

    edit = FilteredEdit(edit, filter=filter.get())

    if backup is not None:
        shutil.copy(pyproject, backup)

    with data.edit_toml(pyproject, metavar="PYPROJECT") as doc:
        ganzua.edit_pyproject(doc, edit)


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


_BlobName = t.NewType("_BlobName", str)


@dataclasses.dataclass(kw_only=True)
class _DataLayer:
    """Joint filesystem/Git access."""

    git: Git | None

    def read(self, resource: pathlib.Path | _BlobName, *, metavar: str) -> str:
        match resource:
            case pathlib.Path() as path:
                try:
                    return path.read_text()
                except FileNotFoundError:
                    msg = f"{metavar}: File `{path}` does not exist."
                    raise clack.UsageError(msg) from None
            case str() as blob_name:
                if self.git is None:  # pragma: no cover
                    msg = f"{metavar}: Cannot read `{blob_name}` because Git support was disabled."
                    raise clack.UsageError(msg)
                return self.git.read_blob(blob_name, mkerr=clack.UsageError)
            case other:
                t.assert_never(other)

    @contextlib.contextmanager
    def edit_toml(
        self, path: pathlib.Path, *, metavar: str
    ) -> t.Generator[toml.Ref, None, None]:
        """Load the TOML file and write it back afterwards."""
        old_contents = self.read(path, metavar=metavar)
        with error_context(f"while parsing {path}"):
            doc = toml.RefRoot.parse(old_contents)

        yield doc

        new_contents = doc.dumps()
        if new_contents != old_contents:
            path.write_text(new_contents)

    def find_pyproject_toml(self, pyproject: pathlib.Path | None) -> pathlib.Path:
        if pyproject is None:
            project_dir = pathlib.Path()
        elif pyproject.is_dir():
            project_dir = pyproject
        else:
            return pyproject

        pyproject = project_dir / "pyproject.toml"
        if not (pyproject.exists() and pyproject.is_file()):
            raise clack.UsageError("Did not find default `pyproject.toml`.")
        return pyproject

    def load_lockfile(
        self, lockfile: str | None, *, metavar: str, project_dir: pathlib.Path
    ) -> ganzua.Lockfile:
        resource = self.find_lockfile(
            lockfile, metavar=metavar, project_dir=project_dir
        )
        data = self.read(resource, metavar=metavar)
        with error_context(f"while parsing {lockfile}"):
            return parse_lockfile(data)

    def find_lockfile(
        self, path_or_revision: str | None, *, metavar: str, project_dir: pathlib.Path
    ) -> pathlib.Path | _BlobName:
        if path_or_revision is None:
            return self.find_lockfile_in_dir(project_dir, metavar=metavar)

        if not self.git:
            pass
        elif path_or_revision.startswith(("/", "./", "../")):
            pass
        elif ":" not in path_or_revision:
            pass
        else:
            return _BlobName(path_or_revision)

        lockfile = pathlib.Path(path_or_revision)
        if lockfile.is_dir():
            return self.find_lockfile_in_dir(lockfile, metavar=metavar)

        return lockfile

    def find_lockfile_in_dir(
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
                err = clack.UsageError(
                    f"Could not infer `{metavar}` for `{project_dir}`."
                )
                for f in existing_lockfiles:
                    err.add_note(f"Candidate lockfile: {shlex.quote(str(f))}")
                raise err
