import pathlib
import secrets
import shutil

import pydantic
import pytest
from inline_snapshot import snapshot

import ganzua

from . import resources
from .helpers import parametrized


def test_can_load_empty_file() -> None:
    with pytest.raises(pydantic.ValidationError):
        ganzua.lockfile_from(resources.EMPTY)


def test_can_load_old_uv() -> None:
    lock = ganzua.lockfile_from(resources.OLD_UV_LOCKFILE)
    assert lock == snapshot(
        {
            "example": {"version": "0.1.0"},
            "typing-extensions": {"version": "3.10.0.2"},
        }
    )


def test_can_load_new_uv() -> None:
    lock = ganzua.lockfile_from(resources.NEW_UV_LOCKFILE)
    assert lock == snapshot(
        {
            "annotated-types": {"version": "0.7.0"},
            "example": {"version": "0.1.0"},
            "typing-extensions": {"version": "4.14.1"},
        }
    )


def test_can_load_old_poetry() -> None:
    lock = ganzua.lockfile_from(resources.OLD_POETRY_LOCKFILE)
    assert lock == snapshot(
        {
            "typing-extensions": {"version": "3.10.0.2"},
        }
    )


def test_can_load_new_poetry() -> None:
    lock = ganzua.lockfile_from(resources.NEW_POETRY_LOCKFILE)
    assert lock == snapshot(
        {
            "annotated-types": {"version": "0.7.0"},
            "typing-extensions": {"version": "4.14.1"},
        }
    )


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
    randomized = tmp_path / secrets.token_hex(5)
    shutil.copy(orig, randomized)
    for word in ("uv", "poetry", "lock", "toml"):
        assert word not in randomized.name

    # we get the same result, regardless of filename
    assert ganzua.lockfile_from(randomized) == ganzua.lockfile_from(orig)
