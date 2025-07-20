import json
import pathlib
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

    assert pyproject.read_text() == snapshot("""\
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
""")


@pytest.mark.parametrize("command", ["inspect", "diff"])
def test_schema(command: str) -> None:
    """Can output a JSON schema for a given command."""
    # But we only test that the output is something json-ish
    result = _run(["schema", command])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema == dirty_equals.IsPartialDict()
