import pathlib

from inline_snapshot import snapshot

import ganzua
from ganzua._markdown import md_from_source
from ganzua._package_source import Source, SourceDirect, SourceRegistry
from tests.helpers import example_poetry_lockfile, example_uv_lockfile

from . import resources


def test_can_load_sources_poetry() -> None:
    parsed = ganzua.lockfile_from(resources.SOURCES_POETRY_LOCKFILE)
    assert parsed == snapshot(
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
    assert {
        name: md_from_source(data["source"])
        for name, data in parsed["packages"].items()
    } == snapshot(
        {
            "click": "default",
            "click-example-repo": "<git+https://github.com/pallets/click.git@309ce9178707e1efaf994f191d062edbdffd5ce6#subdirectory=examples/repo>",
            "colorama": "default",
            "coverage": "registry <https://test.pypi.org/simple>",
            "idna": "default",
            "multidict": "<https://files.pythonhosted.org/packages/b7/da/7d22601b625e241d4f23ef1ebff8acfc60da633c9e7e7922e24d10f592b3/multidict-6.7.0-py3-none-any.whl>",
            "propcache": "default",
            "yarl": "pypi",
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
        expected_markdown=snapshot(
            "<https://example.com/foo.tar.gz> (subdirectory: `some/path`)"
        ),
    )


def test_can_load_sources_poetry_pypi(tmp_path: pathlib.Path) -> None:
    _assert_parse_poetry_source(
        tmp_path,
        package_source_toml="""\
type = "pYpI"
""",
        expected_source=snapshot("pypi"),
        expected_markdown=snapshot("pypi"),
    )


def test_can_load_sources_poetry_unknown(tmp_path: pathlib.Path) -> None:
    _assert_parse_poetry_source(
        tmp_path,
        package_source_toml="""\
type = "some-unknown-source-type"
""",
        expected_source=snapshot("other"),
        expected_markdown=snapshot("other"),
    )


def test_can_load_sources_uv() -> None:
    parsed = ganzua.lockfile_from(resources.SOURCES_UV_LOCKFILE)
    assert parsed == snapshot(
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
    assert {
        name: md_from_source(data["source"])
        for name, data in parsed["packages"].items()
    } == snapshot(
        {
            "click": "pypi",
            "click-example-repo": "<git+https://github.com/pallets/click.git@f67abc6fe7dd3d878879a4f004866bf5acefa9b4#subdirectory=examples/repo>",
            "colorama": "pypi",
            "coverage": "registry <https://test.pypi.org/simple>",
            "idna": "pypi",
            "multidict": "<https://files.pythonhosted.org/packages/b7/da/7d22601b625e241d4f23ef1ebff8acfc60da633c9e7e7922e24d10f592b3/multidict-6.7.0-py3-none-any.whl>",
            "propcache": "pypi",
            "sources-uv": "<.>",
            "yarl": "pypi",
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
        expected_markdown=snapshot(
            "<https://example.com/foo.tar.gz> (subdirectory: `some/path`)"
        ),
    )


def test_can_load_sources_uv_unknown(tmp_path: pathlib.Path) -> None:
    _assert_parse_uv_source(
        tmp_path,
        package_source_toml="""{ some-unknown-source-type = true }""",
        expected_source=snapshot("other"),
        expected_markdown=snapshot("other"),
    )


def _assert_parse_poetry_source(
    tmp_path: pathlib.Path,
    package_source_toml: str,
    expected_source: Source,
    expected_markdown: str,
) -> None:
    __tracebackhide__ = True
    lockfile = example_poetry_lockfile(
        tmp_path / "poetry.lock", {"source_toml": package_source_toml}
    )

    parsed = ganzua.lockfile_from(lockfile)
    assert parsed == {
        "packages": {
            "example": {
                "version": "0.1.0",
                "source": expected_source,
            }
        }
    }
    assert md_from_source(parsed["packages"]["example"]["source"]) == expected_markdown


def _assert_parse_uv_source(
    tmp_path: pathlib.Path,
    package_source_toml: str,
    expected_source: Source,
    expected_markdown: str,
) -> None:
    __tracebackhide__ = True
    lockfile = example_uv_lockfile(
        tmp_path / "uv.lock", {"source_toml": package_source_toml}
    )

    parsed = ganzua.lockfile_from(lockfile)
    assert parsed == {
        "packages": {
            "example": {
                "version": "0.1.0",
                "source": expected_source,
            }
        }
    }
    assert md_from_source(parsed["packages"]["example"]["source"]) == expected_markdown
