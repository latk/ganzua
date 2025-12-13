import pathlib
import typing as t
from dataclasses import dataclass

import dirty_equals
import pydantic
import pytest
from inline_snapshot import snapshot

from ganzua.cli import app

from . import resources
from .helpers import example_poetry_lockfile, example_uv_lockfile, parametrized

run = app.testrunner()


@pytest.mark.parametrize("path", [resources.OLD_UV_LOCKFILE, resources.NEW_UV_LOCKFILE])
def test_empty(path: pathlib.Path) -> None:
    assert run.json("diff", path, path) == {
        "packages": {},
        "stat": {"total": 0, "added": 0, "removed": 0, "updated": 0},
    }


def test_json() -> None:
    old = resources.OLD_UV_LOCKFILE
    new = resources.NEW_UV_LOCKFILE
    output = run.json("diff", old, new)
    assert output == snapshot(
        {
            "packages": {
                "annotated-types": {
                    "old": None,
                    "new": {"version": "0.7.0", "source": "pypi"},
                },
                "typing-extensions": {
                    "old": {"version": "3.10.0.2", "source": "pypi"},
                    "new": {"version": "4.14.1", "source": "pypi"},
                    "is_major_change": True,
                },
            },
            "stat": {"total": 2, "added": 1, "removed": 0, "updated": 1},
        }
    )

    # can also pass directories
    assert run.json("diff", old, new.parent) == output
    assert run.json("diff", old.parent, new) == output
    assert run.json("diff", old.parent, new.parent) == output


def test_markdown() -> None:
    old = resources.OLD_UV_LOCKFILE
    new = resources.NEW_UV_LOCKFILE

    assert run.stdout("diff", "--format=markdown", old, new) == snapshot("""\
2 changed packages (1 added, 1 updated)

| package           | old      | new    | notes |
|-------------------|----------|--------|-------|
| annotated-types   | -        | 0.7.0  |       |
| typing-extensions | 3.10.0.2 | 4.14.1 | (M)   |

* (M) major change
""")

    # the same diff in reverse
    assert run.stdout("diff", "--format=markdown", new, old) == snapshot("""\
2 changed packages (1 updated, 1 removed)

| package           | old    | new      | notes   |
|-------------------|--------|----------|---------|
| annotated-types   | 0.7.0  | -        |         |
| typing-extensions | 4.14.1 | 3.10.0.2 | (M) (D) |

* (M) major change
* (D) downgrade
""")


def test_markdown_source_change() -> None:
    """Source changes are noted below the table.

    When multiple entries have the same note, the IDs are deduplicated.
    """
    old = resources.SOURCES_POETRY_LOCKFILE
    new = resources.SOURCES_UV_LOCKFILE

    assert run.stdout("diff", "--format=markdown", old, new) == snapshot("""\
6 changed packages (1 added, 5 updated)

| package            | old   | new   | notes |
|--------------------|-------|-------|-------|
| click              | 8.3.0 | 8.3.0 | (S1)  |
| click-example-repo | 1.0.0 | 1.0.0 | (S2)  |
| colorama           | 0.4.6 | 0.4.6 | (S1)  |
| idna               | 3.11  | 3.11  | (S1)  |
| propcache          | 0.4.1 | 0.4.1 | (S1)  |
| sources-uv         | -     | 0.1.0 |       |

* (S1) source changed from default to pypi
* (S2) source changed from <git+https://github.com/pallets/click.git@309ce9178707e1efaf994f191d062edbdffd5ce6#subdirectory=examples/repo> to <git+https://github.com/pallets/click.git@f67abc6fe7dd3d878879a4f004866bf5acefa9b4#subdirectory=examples/repo>
""")


def test_markdown_no_notes() -> None:
    """If there are no notes, the entire column is omitted."""
    old = resources.NEW_UV_LOCKFILE
    new = resources.MINOR_UV_LOCKFILE

    assert run.stdout("diff", "--format=markdown", old, new) == snapshot("""\
1 changed packages (1 updated)

| package           | old    | new    |
|-------------------|--------|--------|
| typing-extensions | 4.14.1 | 4.15.0 |
""")


def test_markdown_empty() -> None:
    lockfile = resources.NEW_UV_LOCKFILE
    assert run.stdout("diff", "--format=markdown", lockfile, lockfile) == snapshot(
        "0 changed packages\n"
    )


@dataclass
class _Example:
    """Describe and run examples of version changes."""

    old_version: str | None
    new_version: str | None
    extra_diff: dict[t.Literal["is_major_change", "is_downgrade"], t.Literal[True]]

    def actual_diff(self, *, tmp_dir: pathlib.Path) -> pydantic.JsonValue:
        old_lockfile = self._expand_lockfile(
            tmp_dir / "old.lock", version=self.old_version
        )
        new_lockfile = self._expand_lockfile(
            tmp_dir / "new.lock", version=self.new_version
        )
        print("--- OLD LOCKFILE ---")
        print(old_lockfile.read_text())
        print("--- NEW LOCKFILE ---")
        print(new_lockfile.read_text())
        print("--- END ---")
        return run.json("diff", old_lockfile, new_lockfile)

    def expected_diff(self) -> t.Mapping[str, object]:
        return {
            "packages": {
                "example": {
                    "old": self._expand_diff_package(version=self.old_version),
                    "new": self._expand_diff_package(version=self.new_version),
                    **self.extra_diff,
                },
            },
            "stat": {
                "total": 1,
                "added": dirty_equals.IsOneOf(0, 1),
                "removed": dirty_equals.IsOneOf(0, 1),
                "updated": dirty_equals.IsOneOf(0, 1),
            },
        }

    def _expand_diff_package(
        self, *, version: str | None
    ) -> t.Mapping[str, str] | None:
        if version is None:
            return None
        return {"version": version, "source": "pypi"}

    def _expand_lockfile(
        self, dest: pathlib.Path, *, version: str | None
    ) -> pathlib.Path:
        if version is None:
            return example_uv_lockfile(dest)
        return example_uv_lockfile(dest, {"version": version})


@parametrized(
    "example",
    {
        "minor": _Example("1.2.3", "1.3.4", {}),
        "major": _Example("1.2.3", "2.1.0", {"is_major_change": True}),
        "epoch-changed": _Example("1.2.3", "1!1.2.3", {"is_major_change": True}),
        "epoch-zero": _Example("1.2.3", "0!1.2.3", {}),
        "zerover-same": _Example("0.1.2", "0.1.3", {}),
        "zerover-change": _Example("0.1.2", "0.2.0", {"is_major_change": True}),
        "added": _Example(None, "1.2.3", {}),
        "removed": _Example("1.2.3", None, {}),
        "invalid-to-invalid": _Example("foo", "bar", {"is_major_change": True}),
        "valid-to-invalid": _Example("1.2.3", "foo", {"is_major_change": True}),
        "invalid-to-valid": _Example("foo", "1.2.3", {"is_major_change": True}),
    },
)
def test_is_major_change(example: _Example, tmp_path: pathlib.Path) -> None:
    assert example.actual_diff(tmp_dir=tmp_path) == example.expected_diff()


@parametrized(
    "example",
    {
        "upgrade": _Example("1.0.1", "1.3.4", {}),
        "downgrade": _Example("1.3.4", "1.0.1", {"is_downgrade": True}),
    },
)
def test_is_downgrade(example: _Example, tmp_path: pathlib.Path) -> None:
    assert example.actual_diff(tmp_dir=tmp_path) == example.expected_diff()


def test_is_source_change(tmp_path: pathlib.Path) -> None:
    poetry_source_registry = """
type = "legacy"
url = "https://registry.example/"
reference = "example"
"""
    old = example_poetry_lockfile(
        tmp_path / "old.poetry.lock",
        {"name": "same", "version": "1.2.3"},
        {"name": "changed", "version": "1.2.3", "source_toml": "type = 'pypi'"},
    )
    new = example_poetry_lockfile(
        tmp_path / "new.poetry.lock",
        {"name": "same", "version": "1.2.4"},
        {"name": "changed", "version": "1.2.3", "source_toml": poetry_source_registry},
    )
    assert run.json("diff", old, new) == snapshot(
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
