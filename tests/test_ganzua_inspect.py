import contextlib
import pathlib
import secrets

import pydantic
import pytest

from ganzua.cli import app

from . import resources
from .helpers import (
    CLICK_ERROR,
    example_poetry_lockfile,
    example_uv_lockfile,
    parametrized,
    write_file,
)

inspect = app.testrunner().bind("inspect")


def test_rejects_blank_file() -> None:
    with pytest.raises(pydantic.ValidationError):
        inspect(resources.EMPTY, catch_exceptions=False)


def test_can_load_empty_uv(tmp_path: pathlib.Path) -> None:
    lockfile = write_file(tmp_path / "uv.lock", data=example_uv_lockfile())
    assert inspect.json(lockfile) == {"packages": {}}


def test_can_load_empty_poetry(tmp_path: pathlib.Path) -> None:
    lockfile = write_file(tmp_path / "poetry.lock", data=example_poetry_lockfile())
    assert inspect.json(lockfile) == {"packages": {}}


@parametrized(
    "orig",
    {
        "poetry": resources.NEW_POETRY_LOCKFILE,
        "uv": resources.NEW_UV_LOCKFILE,
    },
)
def test_does_not_care_about_filename(
    orig: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    # save the lockfile under a randomized name
    randomized = write_file(tmp_path / secrets.token_hex(5), source=orig)
    for word in ("uv", "poetry", "lock", "toml"):
        assert word not in randomized.name

    # we get the same result, regardless of filename
    assert inspect.json(randomized) == inspect.json(orig)


def test_can_locate_lockfile(tmp_path: pathlib.Path) -> None:
    lockfile = resources.OLD_UV_LOCKFILE
    output = inspect.json(lockfile)

    # can also use a directory
    assert inspect.json(lockfile.parent) == output

    # behavior when no explicit lockfile argument is passed
    with contextlib.chdir(tmp_path):
        # fails in empty directory
        result = inspect(expect_exit=CLICK_ERROR)
        assert "Could not infer `LOCKFILE` for `.`." in result.stderr

        # but finds the lockfile if present
        write_file(tmp_path / "uv.lock", source=lockfile)
        assert inspect.json() == output
