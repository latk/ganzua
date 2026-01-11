import pathlib

from inline_snapshot import snapshot

from ganzua._doctest import example_poetry_lockfile
from ganzua.cli import app

from .helpers import write_file

diff = app.testrunner().bind("diff")


def test_is_source_change(tmp_path: pathlib.Path) -> None:
    poetry_source_registry = """
type = "legacy"
url = "https://registry.example/"
reference = "example"
"""
    old = write_file(
        tmp_path / "old.poetry.lock",
        data=example_poetry_lockfile(
            {"name": "same", "version": "1.2.3"},
            {"name": "changed", "version": "1.2.3", "source_toml": "type = 'pypi'"},
        ),
    )
    new = write_file(
        tmp_path / "new.poetry.lock",
        data=example_poetry_lockfile(
            {"name": "same", "version": "1.2.4"},
            {
                "name": "changed",
                "version": "1.2.3",
                "source_toml": poetry_source_registry,
            },
        ),
    )
    assert diff.json(old, new) == snapshot(
        {
            "stat": {"total": 2, "added": 0, "removed": 0, "updated": 2},
            "packages": {
                "changed": {
                    "old": {"version": "1.2.3", "source": "pypi"},
                    "new": {
                        "version": "1.2.3",
                        "source": {"registry": "https://registry.example/"},
                    },
                    "is_source_change": True,
                },
                "same": {
                    "old": {"version": "1.2.3", "source": "default"},
                    "new": {"version": "1.2.4", "source": "default"},
                },
            },
        }
    )
