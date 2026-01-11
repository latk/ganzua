import contextlib
import pathlib

from inline_snapshot import snapshot

from ganzua._doctest import example_poetry_lockfile, example_uv_lockfile
from ganzua.cli import app

from . import resources
from .helpers import CLICK_ERROR, parametrized, write_file

bump = app.testrunner().bind("constraints", "bump")


@parametrized("want_backup", {"backup": True, "nobackup": False})
def test_bump(tmp_path: pathlib.Path, want_backup: bool) -> None:
    backup = tmp_path / "backup.pyproject.toml"
    pyproject = write_file(
        tmp_path / "pyproject.toml", source=resources.OLD_UV_PYPROJECT
    )
    lockfile = resources.NEW_UV_LOCKFILE

    cmd = bump.bind(f"--lockfile={lockfile}", pyproject)
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
    cmd = bump.bind(f"--lockfile={resources.NEW_UV_LOCKFILE}")
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
    cmd = bump.bind(pyproject)

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

    assert bump.output(f"--lockfile={lockfile}", pyproject) == ""

    assert pyproject.read_text() == resources.NEW_UV_PYPROJECT.read_text()


_CONSTRAINTS_UV_LOCK = example_uv_lockfile(
    {"name": "annotated-types", "version": "0.7.0"},
    {"name": "example", "version": "0.2.0"},
    {"name": "typing-extensions", "version": "4.14.1"},
)
_CONSTRAINTS_POETRY_LOCK = example_poetry_lockfile(
    {"name": "annotated-types", "version": "0.7.0"},
    {"name": "example", "version": "0.2.0"},
    {"name": "typing-extensions", "version": "4.14.1"},
)


def test_pep621(tmp_path: pathlib.Path) -> None:
    lockfile = write_file(tmp_path / "uv.lock", data=_CONSTRAINTS_UV_LOCK)
    pyproject = write_file(
        tmp_path / "pyproject.toml", data=resources.CONSTRAINTS_PYPROJECT_CONTENTS
    )
    assert bump.output(f"--lockfile={lockfile}", pyproject) == ""
    assert pyproject.read_text() == snapshot("""\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "Typing.Extensions>=4,<5",  # moar type annotations
    "merrily-ignored",
    [42, "also ignored"],  # we ignore invalid junk
]

[project.optional-dependencies]
extra1 = [
    "annotated-types>=0.7.0,==0.7.*",
]
extra2 = false  # known invalid
extra3 = ["ndr"]

[dependency-groups]
group-a = ["typing-extensions~=4.14"]
group-b = [{include-group = "group-a"}, "annotated-types~=0.7.0"]
""")


def test_poetry(tmp_path: pathlib.Path) -> None:
    lockfile = write_file(tmp_path / "uv.lock", data=_CONSTRAINTS_POETRY_LOCK)
    pyproject = write_file(
        tmp_path / "pyproject.toml",
        data=resources.CONSTRAINTS_POETRY_PYPROJECT_CONTENTS,
    )
    assert bump.output(f"--lockfile={lockfile}", pyproject) == ""

    assert pyproject.read_text() == snapshot("""\
[tool.poetry.dependencies]
Typing_Extensions = "^4.14"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "^4.14" }
already-unconstrained = "*"
""")


def test_empty(tmp_path: pathlib.Path) -> None:
    lockfile = write_file(tmp_path / "uv.lock", data=_CONSTRAINTS_UV_LOCK)
    pyproject = write_file(tmp_path / "pyproject.toml", data="")
    assert bump.output(f"--lockfile={lockfile}", pyproject) == ""

    assert pyproject.read_text() == ""
