import contextlib
import pathlib

from inline_snapshot import snapshot

from ganzua.cli import app

from . import resources
from .helpers import CLICK_ERROR, parametrized, write_file

run = app.testrunner()


@parametrized("want_backup", {"backup": True, "nobackup": False})
def test_bump(tmp_path: pathlib.Path, want_backup: bool) -> None:
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


def test_has_default_pyproject(tmp_path: pathlib.Path) -> None:
    cmd = run.bind("constraints", "bump", f"--lockfile={resources.NEW_UV_LOCKFILE}")
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


def test_finds_default_lockfile(tmp_path: pathlib.Path) -> None:
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.OLD_UV_PYPROJECT
    )
    cmd = run.bind("constraints", "bump", pyproject)

    # running without a lockfile fails
    result = cmd(expect_exit=CLICK_ERROR)
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
    assert cmd(expect_exit=CLICK_ERROR).stderr == snapshot(f"""\
Usage: ganzua constraints bump [OPTIONS] [PYPROJECT]
Try 'ganzua constraints bump --help' for help.

Error: Could not infer `--lockfile` for `{tmp_path}`.
Note: Candidate lockfile: {tmp_path}/uv.lock
Note: Candidate lockfile: {tmp_path}/poetry.lock
""")


def test_noop(tmp_path: pathlib.Path) -> None:
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.NEW_UV_PYPROJECT
    )
    lockfile = resources.NEW_UV_LOCKFILE

    assert run.output("constraints", "bump", f"--lockfile={lockfile}", pyproject) == ""

    assert pyproject.read_text() == resources.NEW_UV_PYPROJECT.read_text()
