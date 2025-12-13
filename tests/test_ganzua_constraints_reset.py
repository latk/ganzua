import contextlib
import pathlib
import typing as t

import pytest
from inline_snapshot import snapshot

from ganzua.cli import app

from . import resources
from .helpers import CLICK_ERROR, parametrized, write_file

reset = app.testrunner().bind("constraints", "reset")


@parametrized("want_backup", {"backup": True, "nobackup": False})
def test_reset(tmp_path: pathlib.Path, want_backup: bool) -> None:
    backup = tmp_path / "backup.pyproject.toml"
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.NEW_UV_PYPROJECT
    )

    cmd = reset.bind(pyproject)
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
def test_reset_to_minimum(
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

    assert reset.stdout("--to=minimum", f"--lockfile={lockfile}", pyproject) == ""

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


def test_reset_to_minimum_requires_lockfile(tmp_path: pathlib.Path) -> None:
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.NEW_POETRY_PYPROJECT
    )
    lockfile = resources.NEW_POETRY_LOCKFILE

    cmd = reset.bind("--to=minimum", pyproject)

    # fails without --lockfile
    assert cmd.output(expect_exit=CLICK_ERROR) == snapshot(f"""\
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


def test_has_default_pyproject(tmp_path: pathlib.Path) -> None:
    cmd = reset.bind(f"--lockfile={resources.NEW_UV_LOCKFILE}")
    with contextlib.chdir(tmp_path):
        # running in an empty tempdir fails
        result = cmd(expect_exit=CLICK_ERROR)
        assert "Did not find default `pyproject.toml`." in result.output

        # but a `pyproject.toml` in the CWD is picked up automatically
        pyproject = write_file("pyproject.toml", source=resources.OLD_UV_PYPROJECT)
        expected_output = cmd.output(pyproject)
        assert cmd.output() == expected_output

    # it's also possible to specify just the directory
    assert cmd.output(tmp_path) == expected_output
