import contextlib
import importlib.metadata
import json
import pathlib
import re
import subprocess
import typing as t

import click.testing
import dirty_equals
import pytest
from inline_snapshot import external_file, snapshot

from ganzua._edit_requirement import UpdateRequirement
from ganzua._pyproject import apply_one_pep508_edit
from ganzua.cli import app

from . import resources

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


def _run(args: t.Sequence[str], *, expect_exit: int = 0) -> click.testing.Result:
    __tracebackhide__ = True
    result = click.testing.CliRunner().invoke(app.click, args)
    print(result.output)
    assert result.exit_code == expect_exit
    return result


def _assert_result_eq(left: click.testing.Result, right: click.testing.Result) -> None:
    __tracebackhide__ = True
    assert (left.exit_code, left.output) == (right.exit_code, right.output)


def test_entrypoint() -> None:
    with pytest.raises(SystemExit) as errinfo:
        app(["help"])
    assert errinfo.value.code == 0


def test_inspect(tmp_path: pathlib.Path) -> None:
    lockfile = resources.OLD_UV_LOCKFILE
    output = _run(["inspect", str(lockfile)]).stdout
    assert json.loads(output) == snapshot(
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
    assert _run(["inspect", str(lockfile.parent)]).output == output

    # behavior when no explicit lockfile argument is passed
    with contextlib.chdir(tmp_path):
        # fails in empty directory
        result = _run(["inspect"], expect_exit=_CLICK_ERROR)
        assert "Could not infer `LOCKFILE` for `.`." in result.stderr

        # but finds the lockfile if present
        (tmp_path / "uv.lock").write_bytes(lockfile.read_bytes())
        assert _run(["inspect"]).output == output


def test_inspect_markdown() -> None:
    result = _run(["inspect", "--format=markdown", str(resources.OLD_UV_LOCKFILE)])
    assert result.stdout == snapshot(
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
    output = _run(["diff", str(old), str(new)]).output
    assert json.loads(output) == snapshot(
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
    assert _run(["diff", str(old), str(new.parent)]).output == output
    assert _run(["diff", str(old.parent), str(new)]).output == output
    assert _run(["diff", str(old.parent), str(new.parent)]).output == output


def test_diff_markdown() -> None:
    old = str(resources.OLD_UV_LOCKFILE)
    new = str(resources.NEW_UV_LOCKFILE)

    result = _run(["diff", "--format=markdown", old, new])
    assert result.stdout == snapshot("""\
2 changed packages (1 added, 1 updated)

| package           | old      | new    | notes |
|-------------------|----------|--------|-------|
| annotated-types   | -        | 0.7.0  |       |
| typing-extensions | 3.10.0.2 | 4.14.1 | (M)   |

* (M) major change
""")

    # the same diff in reverse
    result = _run(["diff", "--format=markdown", new, old])
    assert result.stdout == snapshot("""\
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
    old = str(resources.SOURCES_POETRY_LOCKFILE)
    new = str(resources.SOURCES_UV_LOCKFILE)

    result = _run(["diff", "--format=markdown", old, new])
    assert result.stdout == snapshot("""\
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
    old = str(resources.NEW_UV_LOCKFILE)
    new = str(resources.MINOR_UV_LOCKFILE)

    result = _run(["diff", "--format=markdown", old, new])
    assert result.stdout == snapshot("""\
1 changed packages (1 updated)

| package           | old    | new    |
|-------------------|--------|--------|
| typing-extensions | 4.14.1 | 4.15.0 |
""")


def test_diff_markdown_empty() -> None:
    result = _run(
        [
            "diff",
            "--format=markdown",
            str(resources.NEW_UV_LOCKFILE),
            str(resources.NEW_UV_LOCKFILE),
        ]
    )
    assert result.stdout == snapshot("0 changed packages\n")


@pytest.mark.parametrize(
    "want_backup",
    [
        pytest.param(True, id="backup"),
        pytest.param(False, id="nobackup"),
    ],
)
def test_constraints_bump(tmp_path: pathlib.Path, want_backup: bool) -> None:
    backup = tmp_path / "backup.pyproject.toml"
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(resources.OLD_UV_PYPROJECT.read_bytes())

    result = _run(
        [
            "constraints",
            "bump",
            *([f"--backup={backup}"] * want_backup),
            f"--lockfile={resources.NEW_UV_LOCKFILE}",
            str(pyproject),
        ]
    )
    assert result.stdout == ""

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
    cmd = ["constraints", "bump", f"--lockfile={resources.NEW_UV_LOCKFILE}"]
    with contextlib.chdir(tmp_path):
        # running in an empty tempdir fails
        result = _run(cmd, expect_exit=_CLICK_ERROR)
        assert "Did not find default `pyproject.toml`." in result.output

        # but a `pyproject.toml` in the CWD is picked up automatically
        pathlib.Path("pyproject.toml").write_bytes(
            resources.OLD_UV_PYPROJECT.read_bytes()
        )
        output = _run(cmd).output
        expected_output = _run([*cmd, "pyproject.toml"]).output
        assert output == expected_output

    # it's also possible to specify just the directory
    assert _run([*cmd, str(tmp_path)]).output == expected_output


def test_constraints_bump_finds_default_lockfile(tmp_path: pathlib.Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(resources.OLD_UV_PYPROJECT.read_bytes())
    cmd = ["constraints", "bump", str(pyproject)]

    # running without a lockfile fails
    result = _run(cmd, expect_exit=_CLICK_ERROR)
    assert f"Could not infer `--lockfile` for `{tmp_path}`" in result.output

    # but an explicit lockfile succeeds
    lockfile = resources.NEW_UV_LOCKFILE
    expected_output = _run([*cmd, f"--lockfile={lockfile}"]).output

    # also succeeds when the lockfile can be inferred from a directory
    assert _run([*cmd, f"--lockfile={lockfile.parent}"]).output == ""

    # but a `uv.lock` in the same directory is picked up automatically
    (tmp_path / "uv.lock").write_bytes(resources.NEW_UV_LOCKFILE.read_bytes())
    assert _run(cmd).output == expected_output

    # but multiple lockfiles lead to conflicts
    (tmp_path / "poetry.lock").touch()
    result = _run(cmd, expect_exit=_CLICK_ERROR)
    assert result.stderr == snapshot(f"""\
Usage: ganzua constraints bump [OPTIONS] [PYPROJECT]
Try 'ganzua constraints bump --help' for help.

Error: Could not infer `--lockfile` for `{tmp_path}`.
Note: Candidate lockfile: {tmp_path}/uv.lock
Note: Candidate lockfile: {tmp_path}/poetry.lock
""")


def test_constraints_bump_noop(tmp_path: pathlib.Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(resources.NEW_UV_PYPROJECT.read_bytes())

    result = _run(
        [
            "constraints",
            "bump",
            f"--lockfile={resources.NEW_UV_LOCKFILE}",
            str(pyproject),
        ]
    )
    assert result.stdout == ""

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
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(resources.NEW_UV_PYPROJECT.read_bytes())

    result = _run(
        [
            "constraints",
            "reset",
            *([f"--backup={backup}"] * want_backup),
            str(pyproject),
        ]
    )
    assert result.stdout == ""

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
        pyproject.write_bytes(resources.OLD_UV_PYPROJECT.read_bytes())
    elif example == "poetry":
        lockfile = resources.NEW_POETRY_LOCKFILE
        pyproject.write_bytes(resources.NEW_POETRY_PYPROJECT.read_bytes())
    else:  # pragma: no cover
        t.assert_never(example)

    result = _run(
        [
            "constraints",
            "reset",
            "--to=minimum",
            f"--lockfile={lockfile}",
            str(pyproject),
        ]
    )
    assert result.stdout == ""

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
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(resources.NEW_POETRY_PYPROJECT.read_bytes())
    lockfile = resources.NEW_POETRY_LOCKFILE

    cmd = ["constraints", "reset", "--to=minimum", str(pyproject)]

    # fails without --lockfile
    result = _run([*cmd], expect_exit=2)
    assert result.output == snapshot(f"""\
Usage: ganzua constraints reset [OPTIONS] [PYPROJECT]
Try 'ganzua constraints reset --help' for help.

Error: Could not infer `--lockfile` for `{tmp_path}`.
Note: Using `--to=minimum` requires a `--lockfile`.
""")

    # succeeds
    assert _run([*cmd, f"--lockfile={lockfile}"]).output == ""

    # also succeeds when the lockfile can be inferred from a directory
    assert _run([*cmd, f"--lockfile={lockfile.parent}"]).output == ""

    # also succeeds when the lockfile can be inferred from pyproject
    (tmp_path / "uv.lock").write_bytes(lockfile.read_bytes())
    assert _run(cmd).output == ""


def test_constraints_reset_has_default_pyproject(tmp_path: pathlib.Path) -> None:
    cmd = ["constraints", "reset", f"--lockfile={resources.NEW_UV_LOCKFILE}"]
    with contextlib.chdir(tmp_path):
        # running in an empty tempdir fails
        result = _run(cmd, expect_exit=_CLICK_ERROR)
        assert "Did not find default `pyproject.toml`." in result.output

        # but a `pyproject.toml` in the CWD is picked up automatically
        pathlib.Path("pyproject.toml").write_bytes(
            resources.OLD_UV_PYPROJECT.read_bytes()
        )
        output = _run(cmd).output
        expected_output = _run([*cmd, "pyproject.toml"]).output
        assert output == expected_output

    # it's also possible to specify just the directory
    assert _run([*cmd, str(tmp_path)]).output == expected_output


def test_constraints_inspect() -> None:
    result = _run(["constraints", "inspect", str(resources.NEW_UV_PYPROJECT)])
    assert json.loads(result.stdout) == snapshot(
        {
            "requirements": [
                {"name": "annotated-types", "specifier": ">=0.7.0"},
                {"name": "typing-extensions", "specifier": ">=4"},
            ]
        }
    )


def test_constraints_inspect_groups_and_extras() -> None:
    result = _run(
        ["constraints", "inspect", str(resources.POETRY_MULTIPLE_GROUPS_PYPROJECT)]
    )
    assert json.loads(result.stdout) == snapshot(
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
    result = _run(
        ["constraints", "inspect", "--format=markdown", str(resources.NEW_UV_PYPROJECT)]
    )
    assert result.stdout == snapshot("""\
| package           | version |
|-------------------|---------|
| annotated-types   | >=0.7.0 |
| typing-extensions | >=4     |
""")


def test_constraints_inspect_markdown_groups_and_extras() -> None:
    result = _run(
        [
            "constraints",
            "inspect",
            "--format=markdown",
            str(resources.POETRY_MULTIPLE_GROUPS_PYPROJECT),
        ]
    )
    assert result.stdout == snapshot("""\
| package           | version         | group/extra                |
|-------------------|-----------------|----------------------------|
| annotated-types   | <0.8.0          | group `dev`, group `types` |
| annotated-types   | >=0.7.0         |                            |
| typing-extensions | <5.0.0,>=4.15.0 | group `types`              |
| typing-extensions | ^4.15           | extra `dev`, extra `types` |
""")


def test_constraints_inspect_has_default_pyproject(tmp_path: pathlib.Path) -> None:
    cmd = ["constraints", "inspect"]
    with contextlib.chdir(tmp_path):
        # running in an empty tempdir fails
        result = _run(cmd, expect_exit=_CLICK_ERROR)
        assert "Did not find default `pyproject.toml`." in result.output

        # but a `pyproject.toml` in the CWD is picked up automatically
        pathlib.Path("pyproject.toml").write_bytes(
            resources.NEW_UV_PYPROJECT.read_bytes()
        )
        output = _run(cmd).output
        expected_output = _run([*cmd, "pyproject.toml"]).output
        assert output == expected_output

    # it's also possible to specify just the directory
    assert _run([*cmd, str(tmp_path)]).output == expected_output


@pytest.mark.parametrize("command", ["inspect", "diff", "constraints-inspect"])
def test_schema(command: str) -> None:
    """Can output a JSON schema for a given command."""
    # But we only test that the output is something json-ish
    result = _run(["schema", command])
    schema = json.loads(result.stdout)
    assert schema == dirty_equals.IsPartialDict()
    assert schema == external_file(f"schema.{command}.json")


def test_help_mentions_subcommands() -> None:
    result = _run(["help"])
    for cmd in _WELL_KNOWN_COMMANDS:
        assert f" {cmd} " in result.output


def test_help_shows_license() -> None:
    result = _run(["help"])
    assert "Apache-2.0 license" in result.output


def test_no_args_is_help() -> None:
    # The no-args mode does nothing useful,
    # so the exit code should warn users that the tool didn't do anything useful.
    # But don't return an error code when the help was explicitly requested.
    no_args = _run([], expect_exit=_CLICK_ERROR)
    explicit_help = _run(["help"], expect_exit=0)

    assert no_args.output == explicit_help.output


def test_help_explicit() -> None:
    _assert_result_eq(_run(["--help"]), _run(["help"]))


def test_help_subcommand() -> None:
    _assert_result_eq(_run(["inspect", "--help"]), _run(["help", "inspect"]))


def test_help_rejects_unknown_commands() -> None:
    result = _run(["help", "this-is-not-a-command"], expect_exit=_CLICK_ERROR)
    assert result.stderr.startswith("Usage: ganzua help")
    assert result.stderr.endswith("no such subcommand: this-is-not-a-command\n")


def test_help_can_show_subcommands() -> None:
    result = _run(["help", "--all"])
    assert result.output.startswith(_run(["help"]).output)
    for cmd in _WELL_KNOWN_SUBCOMMANDS:
        assert f"\n\nganzua {cmd}\n-----" in result.output
        assert _run(["help", "--all", *cmd.split()]).output in result.output


def test_help_can_use_markdown() -> None:
    result = _run(["help", "help", "--markdown"])
    assert result.output == snapshot(
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


def test_readme() -> None:
    """Test to ensure that the README is up to date.

    * matches current `ganzua help`
    * all doctests produce expected output
    """
    readme = resources.README.read_text()
    readme = _update_usage_section(readme)
    readme = _bump_mentioned_versions(readme)
    readme, executed_examples = _update_bash_doctests(readme)
    assert readme == external_file(str(resources.README), format=".txt")
    assert executed_examples == snapshot(3)


def _update_usage_section(readme: str) -> str:
    begin = "\n<!-- begin usage -->\n"
    end = "\n<!-- end usage -->\n"
    pattern = re.compile(re.escape(begin) + "(.*)" + re.escape(end), flags=re.S)
    up_to_date_usage = _run(["help", "--all", "--markdown"]).output.strip()
    return pattern.sub(f"{begin}\n{up_to_date_usage}\n{end}", readme)


def _bump_mentioned_versions(readme: str) -> str:
    # Subset of the version specifier grammar, originally from PEP 508
    # https://packaging.python.org/en/latest/specifications/dependency-specifiers/#grammar
    version_cmp = r"\s* (?:<=|<|!=|===|==|>=|>|~=)"
    version = r"\s* [a-z0-9_.*+!-]+"
    version_one = rf"{version_cmp} {version} \s*"
    version_many = rf"{version_one} (?:, {version_one})*"  # deny trailing comma
    ganzua_constraint = re.compile(rf"\b ganzua \s* {version_many}", flags=re.X | re.I)

    current_ganzua_version = importlib.metadata.version("ganzua")
    edit = UpdateRequirement(
        {"packages": {"ganzua": {"version": current_ganzua_version, "source": "other"}}}
    )

    return ganzua_constraint.sub(
        lambda m: apply_one_pep508_edit(
            m[0], edit, in_groups=frozenset(), in_extra=None
        ),
        readme,
    )


def _update_bash_doctests(readme: str) -> tuple[str, int]:
    fenced_example_pattern = re.compile(
        r"""
# start a fenced code block with `console` as the info string
^ (?P<delim> [`]{3,}+) [ ]*+ console [ ]*+ \n

# the next line must look like `$ command arg arg`
[$] (?P<command> [^\n]++) \n

# gobble up remaining contents of the fenced section as the output
(?P<output> .*?) \n

# match closing fence
(?P=delim) $
""",
        flags=re.MULTILINE | re.VERBOSE | re.DOTALL,
    )

    executed_examples = 0

    def run_example(m: re.Match) -> str:
        nonlocal executed_examples

        delim = m["delim"]
        command = m["command"].strip()
        assert command.startswith("ganzua ")
        output = _run_shell_command(command).rstrip()
        executed_examples += 1
        return f"{delim}console\n$ {command}\n{output}\n{delim}"

    updated_readme = fenced_example_pattern.sub(run_example, readme)
    return updated_readme, executed_examples


def _run_shell_command(command: str) -> str:
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setenv("TERM", "dumb")  # disable colors

        result = subprocess.run(
            # allow `bash` to be resolved via PATH
            ["bash", "-eu", "-o", "braceexpand", "-c", command],  # noqa: S607
            encoding="utf-8",
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    if result.returncode != 0:  # pragma: no cover
        pytest.fail(
            f"""\
Doctest shell command failed
command: {command}
exit code: {result.returncode}
--- captured stdout
{result.stdout}
--- captured stderr
{result.stderr}
--- end
"""
        )

    return result.stdout
