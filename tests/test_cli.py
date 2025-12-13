import contextlib
import pathlib
import typing as t

import dirty_equals
import pytest
from inline_snapshot import external_file, snapshot

from ganzua.cli import app

from . import resources
from .helpers import write_file

_CLICK_ERROR = 2
"""The exit code used by Click by default."""


_WELL_KNOWN_COMMANDS = (
    "inspect",
    "diff",
    "constraints",
    "schema",
)

_WELL_KNOWN_SUBCOMMANDS = (
    *_WELL_KNOWN_COMMANDS,
    "constraints bump",
    "constraints reset",
    "constraints inspect",
)

run = app.testrunner()


def test_entrypoint() -> None:
    with pytest.raises(SystemExit) as errinfo:
        app(["help"])
    assert errinfo.value.code == 0


def test_inspect(tmp_path: pathlib.Path) -> None:
    lockfile = resources.OLD_UV_LOCKFILE
    output = run.json("inspect", lockfile)
    assert output == snapshot(
        {
            "packages": {
                "example": {
                    "version": "0.1.0",
                    "source": {"direct": "."},
                },
                "typing-extensions": {
                    "version": "3.10.0.2",
                    "source": "pypi",
                },
            }
        }
    )

    # can also use a directory
    assert run.json("inspect", lockfile.parent) == output

    # behavior when no explicit lockfile argument is passed
    with contextlib.chdir(tmp_path):
        # fails in empty directory
        result = run("inspect", expect_exit=_CLICK_ERROR)
        assert "Could not infer `LOCKFILE` for `.`." in result.stderr

        # but finds the lockfile if present
        write_file(tmp_path / "uv.lock", source=lockfile)
        assert run.json("inspect") == output


def test_inspect_markdown() -> None:
    output = run.output("inspect", "--format=markdown", resources.OLD_UV_LOCKFILE)
    assert output == snapshot(
        """\
| package           | version  |
|-------------------|----------|
| example           | 0.1.0    |
| typing-extensions | 3.10.0.2 |
"""
    )


def test_diff() -> None:
    old = resources.OLD_UV_LOCKFILE
    new = resources.NEW_UV_LOCKFILE
    output = run.json("diff", old, new)
    assert output == snapshot(
        {
            "packages": {
                "annotated-types": {
                    "old": None,
                    "new": {"version": "0.7.0", "source": "pypi"},
                },
                "typing-extensions": {
                    "old": {"version": "3.10.0.2", "source": "pypi"},
                    "new": {"version": "4.14.1", "source": "pypi"},
                    "is_major_change": True,
                },
            },
            "stat": {"total": 2, "added": 1, "removed": 0, "updated": 1},
        }
    )

    # can also pass directories
    assert run.json("diff", old, new.parent) == output
    assert run.json("diff", old.parent, new) == output
    assert run.json("diff", old.parent, new.parent) == output


def test_diff_markdown() -> None:
    old = resources.OLD_UV_LOCKFILE
    new = resources.NEW_UV_LOCKFILE

    assert run.stdout("diff", "--format=markdown", old, new) == snapshot("""\
2 changed packages (1 added, 1 updated)

| package           | old      | new    | notes |
|-------------------|----------|--------|-------|
| annotated-types   | -        | 0.7.0  |       |
| typing-extensions | 3.10.0.2 | 4.14.1 | (M)   |

* (M) major change
""")

    # the same diff in reverse
    assert run.stdout("diff", "--format=markdown", new, old) == snapshot("""\
2 changed packages (1 updated, 1 removed)

| package           | old    | new      | notes   |
|-------------------|--------|----------|---------|
| annotated-types   | 0.7.0  | -        |         |
| typing-extensions | 4.14.1 | 3.10.0.2 | (M) (D) |

* (M) major change
* (D) downgrade
""")


def test_diff_markdown_source_change() -> None:
    """Source changes are noted below the table.

    When multiple entries have the same note, the IDs are deduplicated.
    """
    old = resources.SOURCES_POETRY_LOCKFILE
    new = resources.SOURCES_UV_LOCKFILE

    assert run.stdout("diff", "--format=markdown", old, new) == snapshot("""\
6 changed packages (1 added, 5 updated)

| package            | old   | new   | notes |
|--------------------|-------|-------|-------|
| click              | 8.3.0 | 8.3.0 | (S1)  |
| click-example-repo | 1.0.0 | 1.0.0 | (S2)  |
| colorama           | 0.4.6 | 0.4.6 | (S1)  |
| idna               | 3.11  | 3.11  | (S1)  |
| propcache          | 0.4.1 | 0.4.1 | (S1)  |
| sources-uv         | -     | 0.1.0 |       |

* (S1) source changed from default to pypi
* (S2) source changed from <git+https://github.com/pallets/click.git@309ce9178707e1efaf994f191d062edbdffd5ce6#subdirectory=examples/repo> to <git+https://github.com/pallets/click.git@f67abc6fe7dd3d878879a4f004866bf5acefa9b4#subdirectory=examples/repo>
""")


def test_diff_markdown_no_notes() -> None:
    """If there are no notes, the entire column is omitted."""
    old = resources.NEW_UV_LOCKFILE
    new = resources.MINOR_UV_LOCKFILE

    assert run.stdout("diff", "--format=markdown", old, new) == snapshot("""\
1 changed packages (1 updated)

| package           | old    | new    |
|-------------------|--------|--------|
| typing-extensions | 4.14.1 | 4.15.0 |
""")


def test_diff_markdown_empty() -> None:
    lockfile = resources.NEW_UV_LOCKFILE
    assert run.stdout("diff", "--format=markdown", lockfile, lockfile) == snapshot(
        "0 changed packages\n"
    )


@pytest.mark.parametrize(
    "want_backup",
    [
        pytest.param(True, id="backup"),
        pytest.param(False, id="nobackup"),
    ],
)
def test_constraints_bump(tmp_path: pathlib.Path, want_backup: bool) -> None:
    backup = tmp_path / "backup.pyproject.toml"
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.OLD_UV_PYPROJECT
    )
    lockfile = resources.NEW_UV_LOCKFILE

    cmd = run.bind("constraints", "bump", f"--lockfile={lockfile}", pyproject)
    if want_backup:
        cmd = cmd.bind(f"--backup={backup}")

    assert cmd.stdout() == ""

    assert pyproject.read_text() == snapshot(
        """\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "typing-extensions>=4,<5",
]
"""
    )

    if want_backup:
        assert backup.read_text() == resources.OLD_UV_PYPROJECT.read_text()
    else:
        assert not backup.exists()


def test_constraints_bump_has_default_pyproject(tmp_path: pathlib.Path) -> None:
    cmd = run.bind("constraints", "bump", f"--lockfile={resources.NEW_UV_LOCKFILE}")
    with contextlib.chdir(tmp_path):
        # running in an empty tempdir fails
        result = cmd(expect_exit=_CLICK_ERROR)
        assert "Did not find default `pyproject.toml`." in result.output

        # but a `pyproject.toml` in the CWD is picked up automatically
        pyproject = write_file("pyproject.toml", source=resources.OLD_UV_PYPROJECT)
        expected_output = cmd.output(pyproject)
        assert cmd.output() == expected_output

    # it's also possible to specify just the directory
    assert cmd.output(tmp_path) == expected_output


def test_constraints_bump_finds_default_lockfile(tmp_path: pathlib.Path) -> None:
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.OLD_UV_PYPROJECT
    )
    cmd = run.bind("constraints", "bump", pyproject)

    # running without a lockfile fails
    result = cmd(expect_exit=_CLICK_ERROR)
    assert f"Could not infer `--lockfile` for `{tmp_path}`" in result.output

    # but an explicit lockfile succeeds
    lockfile = resources.NEW_UV_LOCKFILE
    expected_output = cmd.output(f"--lockfile={lockfile}")

    # also succeeds when the lockfile can be inferred from a directory
    assert cmd.output(f"--lockfile={lockfile.parent}") == ""

    # but a `uv.lock` in the same directory is picked up automatically
    write_file(tmp_path / "uv.lock", source=resources.NEW_UV_LOCKFILE)
    assert cmd.output() == expected_output

    # but multiple lockfiles lead to conflicts
    (tmp_path / "poetry.lock").touch()
    assert cmd(expect_exit=_CLICK_ERROR).stderr == snapshot(f"""\
Usage: ganzua constraints bump [OPTIONS] [PYPROJECT]
Try 'ganzua constraints bump --help' for help.

Error: Could not infer `--lockfile` for `{tmp_path}`.
Note: Candidate lockfile: {tmp_path}/uv.lock
Note: Candidate lockfile: {tmp_path}/poetry.lock
""")


def test_constraints_bump_noop(tmp_path: pathlib.Path) -> None:
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.NEW_UV_PYPROJECT
    )
    lockfile = resources.NEW_UV_LOCKFILE

    assert run.output("constraints", "bump", f"--lockfile={lockfile}", pyproject) == ""

    assert pyproject.read_text() == resources.NEW_UV_PYPROJECT.read_text()


@pytest.mark.parametrize(
    "want_backup",
    [
        pytest.param(True, id="backup"),
        pytest.param(False, id="nobackup"),
    ],
)
def test_constraints_reset(tmp_path: pathlib.Path, want_backup: bool) -> None:
    backup = tmp_path / "backup.pyproject.toml"
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.NEW_UV_PYPROJECT
    )

    cmd = run.bind("constraints", "reset", pyproject)
    if want_backup:
        cmd = cmd.bind(f"--backup={backup}")
    assert cmd.stdout() == ""

    assert pyproject.read_text() == snapshot(
        """\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "annotated-types",
    "typing-extensions",
]
"""
    )

    if want_backup:
        assert backup.read_text() == resources.NEW_UV_PYPROJECT.read_text()
    else:
        assert not backup.exists()


@pytest.mark.parametrize("example", ["uv", "poetry"])
def test_constraints_reset_to_minimum(
    tmp_path: pathlib.Path, example: t.Literal["uv", "poetry"]
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    if example == "uv":
        lockfile = resources.OLD_POETRY_LOCKFILE
        write_file(pyproject, source=resources.OLD_UV_PYPROJECT)
    elif example == "poetry":
        lockfile = resources.NEW_POETRY_LOCKFILE
        write_file(pyproject, source=resources.NEW_POETRY_PYPROJECT)
    else:  # pragma: no cover
        t.assert_never(example)

    assert (
        run.stdout(
            "constraints", "reset", "--to=minimum", f"--lockfile={lockfile}", pyproject
        )
        == ""
    )

    expected = snapshot(
        {
            "uv": """\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "typing-extensions>=3.10.0.2",
]
""",
            "poetry": """\
[project]
name = "example"
version = "0.1.0"
description = ""
authors = [
    {name = "Your Name",email = "you@example.com"}
]
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "annotated-types>=0.7.0",
    "typing-extensions>=4.14.1",
]


[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
""",
        }
    )
    assert pyproject.read_text() == expected[example]


def test_constraints_reset_to_minimum_requires_lockfile(tmp_path: pathlib.Path) -> None:
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.NEW_POETRY_PYPROJECT
    )
    lockfile = resources.NEW_POETRY_LOCKFILE

    cmd = run.bind("constraints", "reset", "--to=minimum", pyproject)

    # fails without --lockfile
    assert cmd.output(expect_exit=_CLICK_ERROR) == snapshot(f"""\
Usage: ganzua constraints reset [OPTIONS] [PYPROJECT]
Try 'ganzua constraints reset --help' for help.

Error: Could not infer `--lockfile` for `{tmp_path}`.
Note: Using `--to=minimum` requires a `--lockfile`.
""")

    # succeeds
    assert cmd.output(f"--lockfile={lockfile}") == ""

    # also succeeds when the lockfile can be inferred from a directory
    assert cmd.output(f"--lockfile={lockfile.parent}") == ""

    # also succeeds when the lockfile can be inferred from pyproject
    write_file(tmp_path / "uv.lock", source=lockfile)
    assert cmd.output() == ""


def test_constraints_reset_has_default_pyproject(tmp_path: pathlib.Path) -> None:
    cmd = run.bind("constraints", "reset", f"--lockfile={resources.NEW_UV_LOCKFILE}")
    with contextlib.chdir(tmp_path):
        # running in an empty tempdir fails
        result = cmd(expect_exit=_CLICK_ERROR)
        assert "Did not find default `pyproject.toml`." in result.output

        # but a `pyproject.toml` in the CWD is picked up automatically
        pyproject = write_file("pyproject.toml", source=resources.OLD_UV_PYPROJECT)
        expected_output = cmd.output(pyproject)
        assert cmd.output() == expected_output

    # it's also possible to specify just the directory
    assert cmd.output(tmp_path) == expected_output


def test_constraints_inspect() -> None:
    assert run.json("constraints", "inspect", resources.NEW_UV_PYPROJECT) == snapshot(
        {
            "requirements": [
                {"name": "annotated-types", "specifier": ">=0.7.0"},
                {"name": "typing-extensions", "specifier": ">=4"},
            ]
        }
    )


def test_constraints_inspect_groups_and_extras() -> None:
    assert run.json(
        "constraints", "inspect", resources.POETRY_MULTIPLE_GROUPS_PYPROJECT
    ) == snapshot(
        {
            "requirements": [
                {"name": "annotated-types", "specifier": ">=0.7.0"},
                {
                    "name": "annotated-types",
                    "specifier": "<0.8.0",
                    "in_groups": ["dev", "types"],
                },
                {
                    "name": "typing-extensions",
                    "specifier": "<5.0.0,>=4.15.0",
                    "in_groups": ["types"],
                },
                {
                    "name": "typing-extensions",
                    "specifier": "^4.15",
                    "in_extras": ["dev", "types"],
                },
            ]
        }
    )


def test_constraints_inspect_markdown() -> None:
    assert run.stdout(
        "constraints", "inspect", "--format=markdown", resources.NEW_UV_PYPROJECT
    ) == snapshot("""\
| package           | version |
|-------------------|---------|
| annotated-types   | >=0.7.0 |
| typing-extensions | >=4     |
""")


def test_constraints_inspect_markdown_groups_and_extras() -> None:
    assert run.stdout(
        "constraints",
        "inspect",
        "--format=markdown",
        resources.POETRY_MULTIPLE_GROUPS_PYPROJECT,
    ) == snapshot("""\
| package           | version         | group/extra                |
|-------------------|-----------------|----------------------------|
| annotated-types   | <0.8.0          | group `dev`, group `types` |
| annotated-types   | >=0.7.0         |                            |
| typing-extensions | <5.0.0,>=4.15.0 | group `types`              |
| typing-extensions | ^4.15           | extra `dev`, extra `types` |
""")


def test_constraints_inspect_has_default_pyproject(tmp_path: pathlib.Path) -> None:
    cmd = run.bind("constraints", "inspect")
    with contextlib.chdir(tmp_path):
        # running in an empty tempdir fails
        result = cmd(expect_exit=_CLICK_ERROR)
        assert "Did not find default `pyproject.toml`." in result.output

        # but a `pyproject.toml` in the CWD is picked up automatically
        pyproject = write_file("pyproject.toml", source=resources.NEW_UV_PYPROJECT)
        expected_output = cmd.output(pyproject)
        assert cmd.output() == expected_output

    # it's also possible to specify just the directory
    assert cmd.output(tmp_path) == expected_output


@pytest.mark.parametrize("command", ["inspect", "diff", "constraints-inspect"])
def test_schema(command: str) -> None:
    """Can output a JSON schema for a given command."""
    # But we only test that the output is something json-ish
    schema = run.json("schema", command)
    assert schema == dirty_equals.IsPartialDict()
    assert schema == external_file(f"schema.{command}.json")


def test_help_mentions_subcommands() -> None:
    output = run.output("help")
    for cmd in _WELL_KNOWN_COMMANDS:
        assert f" {cmd} " in output


def test_help_shows_license() -> None:
    assert "Apache-2.0 license" in run.output("help")


def test_no_args_is_help() -> None:
    # The no-args mode does nothing useful,
    # so the exit code should warn users that the tool didn't do anything useful.
    # But don't return an error code when the help was explicitly requested.
    no_args = run.output(expect_exit=_CLICK_ERROR)
    explicit_help = run.output("help", expect_exit=0)

    assert no_args == explicit_help


def test_help_explicit() -> None:
    assert run.output("--help") == run.output("help")


def test_help_subcommand() -> None:
    assert run.output("inspect", "--help") == run.output("help", "inspect")


def test_help_rejects_unknown_commands() -> None:
    result = run("help", "this-is-not-a-command", expect_exit=_CLICK_ERROR)
    assert result.stderr.startswith("Usage: ganzua help")
    assert result.stderr.endswith("no such subcommand: this-is-not-a-command\n")


def test_help_can_show_subcommands() -> None:
    all_help = run.output("help", "--all")
    assert all_help.startswith(run.output("help"))
    for cmd in _WELL_KNOWN_SUBCOMMANDS:
        assert f"\n\nganzua {cmd}\n-----" in all_help
        assert run.output("help", "--all", *cmd.split()) in all_help


def test_help_can_use_markdown() -> None:
    assert run.output("help", "help", "--markdown") == snapshot(
        """\
Usage: `ganzua help [OPTIONS] [SUBCOMMAND]...`

Show help for the application or a specific subcommand.

**Options:**

* `--all`
  Also show help for all subcommands.
* `--markdown`
  Output help in Markdown format.
"""
    )
