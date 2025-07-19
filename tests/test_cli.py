import json
import typing as t

import click.testing
import dirty_equals
import pytest
import typer.testing
from inline_snapshot import snapshot

from lockinator.cli import app

from . import resources


def _run(args: t.Sequence[str]) -> click.testing.Result:
    result = typer.testing.CliRunner().invoke(app, args)
    print(result.output)
    return result


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


@pytest.mark.parametrize("command", ["inspect", "diff"])
def test_schema(command: str) -> None:
    """Can output a JSON schema for a given command."""
    # But we only test that the output is something json-ish
    result = _run(["schema", command])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema == dirty_equals.IsPartialDict()
