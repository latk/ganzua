import json
import pathlib
import typing as t

import click.testing
import dirty_equals
import pytest
from inline_snapshot import snapshot

from ganzua.cli import app

from . import resources

_CLICK_ERROR = 2
"""The exit code used by Click by default."""


_WELL_KNOWN_COMMANDS = [
    "inspect",
    "diff",
    "update-constraints",
    "remove-constraints",
    "schema",
]


def _run(args: t.Sequence[str]) -> click.testing.Result:
    result = click.testing.CliRunner().invoke(app.click, args)
    print(result.output)
    return result


def _assert_result_eq(left: click.testing.Result, right: click.testing.Result) -> None:
    __tracebackhide__ = True
    assert (left.exit_code, left.output) == (right.exit_code, right.output)


def test_entrypoint() -> None:
    with pytest.raises(SystemExit) as errinfo:
        app(["help"])
    assert errinfo.value.code == 0


def test_inspect() -> None:
    result = _run(["inspect", str(resources.OLD_UV_LOCKFILE)])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == snapshot(
        {
            "example": {"version": "0.1.0"},
            "typing-extensions": {"version": "3.10.0.2"},
        }
    )


def test_diff() -> None:
    result = _run(
        ["diff", str(resources.OLD_UV_LOCKFILE), str(resources.NEW_UV_LOCKFILE)]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == snapshot(
        {
            "annotated-types": {"old": None, "new": "0.7.0"},
            "typing-extensions": {"old": "3.10.0.2", "new": "4.14.1"},
        }
    )


def test_update_constraints(tmp_path: pathlib.Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(resources.OLD_UV_PYPROJECT.read_bytes())

    result = _run(
        ["update-constraints", str(resources.NEW_UV_LOCKFILE), str(pyproject)]
    )
    assert result.exit_code == 0
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


def test_update_constraints_noop(tmp_path: pathlib.Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(resources.NEW_UV_PYPROJECT.read_bytes())

    result = _run(
        ["update-constraints", str(resources.NEW_UV_LOCKFILE), str(pyproject)]
    )
    assert result.exit_code == 0
    assert result.stdout == ""

    assert pyproject.read_text() == resources.NEW_UV_PYPROJECT.read_text()


def test_remove_constraints(tmp_path: pathlib.Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(resources.NEW_UV_PYPROJECT.read_bytes())

    result = _run(["remove-constraints", str(pyproject)])
    assert result.exit_code == 0
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


@pytest.mark.parametrize("command", ["inspect", "diff"])
def test_schema(command: str) -> None:
    """Can output a JSON schema for a given command."""
    # But we only test that the output is something json-ish
    result = _run(["schema", command])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema == dirty_equals.IsPartialDict()


def test_help_mentions_subcommands() -> None:
    result = _run(["help"])
    assert result.exit_code == 0
    for cmd in _WELL_KNOWN_COMMANDS:
        assert f" {cmd} " in result.output


def test_help_shows_license() -> None:
    result = _run(["help"])
    assert result.exit_code == 0
    assert "Apache-2.0 license" in result.output


def test_no_args_is_help() -> None:
    no_args = _run([])
    explicit_help = _run(["help"])

    # The no-args mode does nothing useful,
    # so the exit code should warn users that the tool didn't do anything useful.
    # But don't return an error code when the help was explicitly requested.
    assert no_args.exit_code == _CLICK_ERROR
    assert explicit_help.exit_code == 0

    assert no_args.output == explicit_help.output


def test_help_explicit() -> None:
    _assert_result_eq(_run(["--help"]), _run(["help"]))


def test_help_subcommand() -> None:
    _assert_result_eq(_run(["inspect", "--help"]), _run(["help", "inspect"]))


def test_help_rejects_unknown_commands() -> None:
    result = _run(["help", "this-is-not-a-command"])
    assert result.exit_code == _CLICK_ERROR
    assert result.stderr.startswith("Usage: ganzua help")
    assert result.stderr.endswith("no such subcommand: this-is-not-a-command\n")


def test_help_can_show_subcommands() -> None:
    result = _run(["help", "--all"])
    assert result.exit_code == 0
    assert result.output.startswith(_run(["help"]).output)
    for cmd in _WELL_KNOWN_COMMANDS:
        assert f"\n\nganzua {cmd}\n-----" in result.output
        assert _run(["help", "--all", cmd]).output in result.output


def test_help_can_use_markdown() -> None:
    result = _run(["help", "help", "--markdown"])
    assert result.exit_code == 0
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
