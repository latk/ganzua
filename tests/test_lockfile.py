import pathlib
import secrets
import shutil

import pydantic
import pytest
from inline_snapshot import snapshot

import ganzua
from ganzua._package_source import Source, SourceDirect, SourceRegistry

from . import resources
from .helpers import parametrized


def test_can_load_empty_file() -> None:
    with pytest.raises(pydantic.ValidationError):
        ganzua.lockfile_from(resources.EMPTY)


def test_can_load_old_uv() -> None:
    lock = ganzua.lockfile_from(resources.OLD_UV_LOCKFILE)
    assert lock == snapshot(
        {
            "packages": {
                "example": {"version": "0.1.0", "source": SourceDirect(direct=".")},
                "typing-extensions": {"version": "3.10.0.2", "source": "pypi"},
            }
        }
    )


def test_can_load_new_uv() -> None:
    lock = ganzua.lockfile_from(resources.NEW_UV_LOCKFILE)
    assert lock == snapshot(
        {
            "packages": {
                "annotated-types": {"version": "0.7.0", "source": "pypi"},
                "example": {"version": "0.1.0", "source": SourceDirect(direct=".")},
                "typing-extensions": {"version": "4.14.1", "source": "pypi"},
            }
        }
    )


def test_can_load_old_poetry() -> None:
    lock = ganzua.lockfile_from(resources.OLD_POETRY_LOCKFILE)
    assert lock == snapshot(
        {
            "packages": {
                "typing-extensions": {"version": "3.10.0.2", "source": "default"},
            }
        }
    )


def test_can_load_new_poetry() -> None:
    lock = ganzua.lockfile_from(resources.NEW_POETRY_LOCKFILE)
    assert lock == snapshot(
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
    randomized = tmp_path / secrets.token_hex(5)
    shutil.copy(orig, randomized)
    for word in ("uv", "poetry", "lock", "toml"):
        assert word not in randomized.name

    # we get the same result, regardless of filename
    assert ganzua.lockfile_from(randomized) == ganzua.lockfile_from(orig)


def test_can_load_sources_poetry() -> None:
    assert ganzua.lockfile_from(resources.SOURCES_POETRY_LOCKFILE) == snapshot(
        {
            "packages": {
                "click": {"version": "8.3.0", "source": "default"},
                "click-example-repo": {
                    "version": "1.0.0",
                    "source": SourceDirect(
                        direct="git+https://github.com/pallets/click.git@309ce9178707e1efaf994f191d062edbdffd5ce6#subdirectory=examples/repo"
                    ),
                },
                "colorama": {"version": "0.4.6", "source": "default"},
                "coverage": {
                    "version": "7.10.7",
                    "source": SourceRegistry(registry="https://test.pypi.org/simple"),
                },
                "idna": {"version": "3.11", "source": "default"},
                "multidict": {
                    "version": "6.7.0",
                    "source": SourceDirect(
                        direct="https://files.pythonhosted.org/packages/b7/da/7d22601b625e241d4f23ef1ebff8acfc60da633c9e7e7922e24d10f592b3/multidict-6.7.0-py3-none-any.whl"
                    ),
                },
                "propcache": {"version": "0.4.1", "source": "default"},
                "yarl": {"version": "1.22.0", "source": "pypi"},
            }
        }
    )


def test_can_load_sources_poetry_direct_subdirectory(tmp_path: pathlib.Path) -> None:
    _assert_parse_poetry_source(
        tmp_path,
        package_source_toml="""\
type = "url"
url = "https://example.com/foo.tar.gz"
subdirectory = "some/path"
        """,
        expected_source=snapshot(
            SourceDirect(
                direct="https://example.com/foo.tar.gz", subdirectory="some/path"
            )
        ),
    )


def test_can_load_sources_poetry_pypi(tmp_path: pathlib.Path) -> None:
    _assert_parse_poetry_source(
        tmp_path,
        package_source_toml="""\
type = "pYpI"
""",
        expected_source=snapshot("pypi"),
    )


def test_can_load_sources_poetry_unknown(tmp_path: pathlib.Path) -> None:
    _assert_parse_poetry_source(
        tmp_path,
        package_source_toml="""\
type = "some-unknown-source-type"
""",
        expected_source=snapshot("other"),
    )


def test_can_load_sources_uv() -> None:
    assert ganzua.lockfile_from(resources.SOURCES_UV_LOCKFILE) == snapshot(
        {
            "packages": {
                "click": {"version": "8.3.0", "source": "pypi"},
                "click-example-repo": {
                    "version": "1.0.0",
                    "source": SourceDirect(
                        direct="git+https://github.com/pallets/click.git@f67abc6fe7dd3d878879a4f004866bf5acefa9b4#subdirectory=examples/repo"
                    ),
                },
                "colorama": {"version": "0.4.6", "source": "pypi"},
                "coverage": {
                    "version": "7.10.7",
                    "source": SourceRegistry(registry="https://test.pypi.org/simple"),
                },
                "idna": {"version": "3.11", "source": "pypi"},
                "multidict": {
                    "version": "6.7.0",
                    "source": SourceDirect(
                        direct="https://files.pythonhosted.org/packages/b7/da/7d22601b625e241d4f23ef1ebff8acfc60da633c9e7e7922e24d10f592b3/multidict-6.7.0-py3-none-any.whl"
                    ),
                },
                "propcache": {"version": "0.4.1", "source": "pypi"},
                "sources-uv": {"version": "0.1.0", "source": SourceDirect(direct=".")},
                "yarl": {"version": "1.22.0", "source": "pypi"},
            }
        }
    )


def test_can_load_sources_uv_direct_subdirectory(tmp_path: pathlib.Path) -> None:
    _assert_parse_uv_source(
        tmp_path,
        package_source_toml="""{ url = "https://example.com/foo.tar.gz", subdirectory = "some/path" }""",
        expected_source=snapshot(
            SourceDirect(
                direct="https://example.com/foo.tar.gz", subdirectory="some/path"
            )
        ),
    )


def test_can_load_sources_uv_unknown(tmp_path: pathlib.Path) -> None:
    _assert_parse_uv_source(
        tmp_path,
        package_source_toml="""{ some-unknown-source-type = true }""",
        expected_source=snapshot("other"),
    )


def _assert_parse_poetry_source(
    tmp_path: pathlib.Path, package_source_toml: str, expected_source: Source
) -> None:
    __tracebackhide__ = True
    lockfile = tmp_path / "poetry.lock"
    lockfile.write_text(
        f"""\
[[package]]
name = "example"
version = "0.1.0"

[package.source]
{package_source_toml}

[metadata]
lock-version = "2.1"
python-versions = ">=3.12"
content-hash = "0000000000000000000000000000000000000000000000000000000000000000"
"""
    )

    assert ganzua.lockfile_from(lockfile) == {
        "packages": {
            "example": {
                "version": "0.1.0",
                "source": expected_source,
            }
        }
    }


def _assert_parse_uv_source(
    tmp_path: pathlib.Path, package_source_toml: str, expected_source: Source
) -> None:
    __tracebackhide__ = True
    lockfile = tmp_path / "poetry.lock"
    lockfile.write_text(
        f"""\
version = 1
revision = 3
requires-python = ">=3.12"

[[package]]
name = "example"
version = "0.1.0"
source = {package_source_toml}
"""
    )

    assert ganzua.lockfile_from(lockfile) == {
        "packages": {
            "example": {
                "version": "0.1.0",
                "source": expected_source,
            }
        }
    }
