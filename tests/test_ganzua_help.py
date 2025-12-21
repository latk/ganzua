import dirty_equals
import pytest
from inline_snapshot import external_file, snapshot

from ganzua.cli import app

from . import resources
from .helpers import CLICK_ERROR

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


@pytest.mark.parametrize("command", ["inspect", "diff", "constraints-inspect"])
def test_schema(command: str) -> None:
    """Can output a JSON schema for a given command."""
    # But we only test that the output is something json-ish
    schema = run.json("schema", command)
    assert schema == dirty_equals.IsPartialDict()
    assert schema == external_file(resources.DOCS / f"cli/schema.{command}.json")


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
    no_args = run.output(expect_exit=CLICK_ERROR)
    explicit_help = run.output("help", expect_exit=0)

    assert no_args == explicit_help


def test_help_explicit() -> None:
    assert run.output("--help") == run.output("help")


def test_help_subcommand() -> None:
    assert run.output("inspect", "--help") == run.output("help", "inspect")


def test_help_rejects_unknown_commands() -> None:
    result = run("help", "this-is-not-a-command", expect_exit=CLICK_ERROR)
    assert result.stderr.startswith("Usage: ganzua help")
    assert result.stderr.endswith("no such subcommand: this-is-not-a-command\n")


def test_help_can_show_subcommands() -> None:
    all_help = run.output("help", "--all")
    assert all_help.startswith(run.output("help"))
    for cmd in _WELL_KNOWN_SUBCOMMANDS:
        assert f"\n\nganzua {cmd}\n-----" in all_help
        assert run.output("help", "--all", *cmd.split()) in all_help


def test_help_can_use_markdown() -> None:
    assert run.output("help", "--markdown") == snapshot(
        """\
Usage: `ganzua [OPTIONS] COMMAND [ARGS]...`

Inspect Python dependency lockfiles (uv and Poetry).

**Options:**

* `--help`
  Show this help message and exit.

**Commands:**

* `help`
  Show help for the application or a specific subcommand.
* `inspect`
  Inspect a lockfile.
* `diff`
  Compare two lockfiles.
* `constraints`
  Work with `pyproject.toml` constraints.
* `schema`
  Show the JSON schema for the output of the given command.

For more information, see the Ganzua website at "<https://github.com/latk/ganzua>".

Ganzua is licensed under the Apache-2.0 license.
"""
    )
