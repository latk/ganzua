import contextlib
import pathlib
import secrets

import pydantic
import pytest
from inline_snapshot import snapshot

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
    lockfile = example_uv_lockfile(tmp_path / "uv.lock")
    assert inspect.json(lockfile) == {"packages": {}}


def test_can_load_empty_poetry(tmp_path: pathlib.Path) -> None:
    lockfile = example_poetry_lockfile(tmp_path / "poetry.lock")
    assert inspect.json(lockfile) == {"packages": {}}


def test_can_load_old_uv() -> None:
    assert inspect.json(resources.OLD_UV_LOCKFILE) == snapshot(
        {
            "packages": {
                "example": {"version": "0.1.0", "source": {"direct": "."}},
                "typing-extensions": {"version": "3.10.0.2", "source": "pypi"},
            }
        }
    )


def test_can_load_new_uv() -> None:
    assert inspect.json(resources.NEW_UV_LOCKFILE) == snapshot(
        {
            "packages": {
                "annotated-types": {"version": "0.7.0", "source": "pypi"},
                "example": {"version": "0.1.0", "source": {"direct": "."}},
                "typing-extensions": {"version": "4.14.1", "source": "pypi"},
            }
        }
    )


def test_can_load_old_poetry() -> None:
    assert inspect.json(resources.OLD_POETRY_LOCKFILE) == snapshot(
        {
            "packages": {
                "typing-extensions": {"version": "3.10.0.2", "source": "default"},
            }
        }
    )


def test_can_load_new_poetry() -> None:
    assert inspect.json(resources.NEW_POETRY_LOCKFILE) == snapshot(
        {
            "packages": {
                "annotated-types": {"version": "0.7.0", "source": "default"},
                "typing-extensions": {"version": "4.14.1", "source": "default"},
            }
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


def test_markdown() -> None:
    output = inspect.output("--format=markdown", resources.OLD_UV_LOCKFILE)
    assert output == snapshot(
        """\
| package           | version  |
|-------------------|----------|
| example           | 0.1.0    |
| typing-extensions | 3.10.0.2 |
"""
    )


def test_can_parse_package_without_version_uv() -> None:
    """Test for <https://github.com/latk/ganzua/issues/4>."""
    assert inspect.json(resources.SETUPTOOLS_DYNAMIC_VERSION_LOCKFILE) == snapshot(
        {
            "packages": {
                "setuptools-dynamic-version": {
                    "version": "0+undefined",
                    "source": {"direct": "."},
                }
            }
        }
    )
