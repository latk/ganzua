import json

import typer.testing
from inline_snapshot import snapshot

from lockinator.cli import app

from . import resources

_RUNNER = typer.testing.CliRunner()


def test_inspect() -> None:
    result = _RUNNER.invoke(app, ["inspect", str(resources.OLD_UV_LOCKFILE)])
    assert result.exit_code == 0
    assert json.loads(result.output) == snapshot(
        {
            "example": {"version": "0.1.0"},
            "typing-extensions": {"version": "3.10.0.2"},
        }
    )


def test_diff() -> None:
    result = _RUNNER.invoke(
        app, ["diff", str(resources.OLD_UV_LOCKFILE), str(resources.NEW_UV_LOCKFILE)]
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == snapshot(
        {
            "annotated-types": {"old": None, "new": "0.7.0"},
            "typing-extensions": {"old": "3.10.0.2", "new": "4.14.1"},
        }
    )
