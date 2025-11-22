import typing as t
from dataclasses import dataclass
from importlib.resources.abc import Traversable

import dirty_equals
import pydantic
import pytest
from inline_snapshot import snapshot

from ganzua import diff
from ganzua._lockfile import Lockfile, lockfile_from
from ganzua._package_source import SourceRegistry
from ganzua.cli import DIFF_SCHEMA

from . import resources
from .helpers import parametrized


@pytest.mark.parametrize("path", [resources.OLD_UV_LOCKFILE, resources.NEW_UV_LOCKFILE])
def test_comparing_self_is_empty(path: Traversable) -> None:
    assert _json_diff_path(path, path) == {
        "packages": {},
        "stat": {"total": 0, "added": 0, "removed": 0, "updated": 0},
    }


def test_uv() -> None:
    assert _json_diff_path(
        resources.OLD_UV_LOCKFILE, resources.NEW_UV_LOCKFILE
    ) == snapshot(
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


@dataclass
class _Example:
    old_version: str | None
    new_version: str | None
    extra_diff: dict[t.Literal["is_major_change", "is_downgrade"], t.Literal[True]]

    def expand(self) -> tuple[Lockfile, Lockfile, t.Mapping[str, object]]:
        """Expand the example into `(old_lockfile, new_lockfile, expected_diff)`."""
        old_lockfile: Lockfile = {"packages": {}}
        new_lockfile: Lockfile = {"packages": {}}
        old_package = None
        new_package = None
        if self.old_version is not None:
            old_package = old_lockfile["packages"]["example"] = {
                "version": self.old_version,
                "source": "default",
            }
        if self.new_version is not None:
            new_package = new_lockfile["packages"]["example"] = {
                "version": self.new_version,
                "source": "default",
            }
        expected_diff: t.Mapping[str, object] = {
            "packages": {
                "example": {"old": old_package, "new": new_package, **self.extra_diff},
            },
            "stat": {
                "total": 1,
                "added": dirty_equals.IsOneOf(0, 1),
                "removed": dirty_equals.IsOneOf(0, 1),
                "updated": dirty_equals.IsOneOf(0, 1),
            },
        }
        return old_lockfile, new_lockfile, expected_diff


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
def test_is_major_change(example: _Example) -> None:
    old_lockfile, new_lockfile, expected_diff = example.expand()
    assert _json_diff_lockfile(old_lockfile, new_lockfile) == expected_diff


@parametrized(
    "example",
    {
        "upgrade": _Example("1.0.1", "1.3.4", {}),
        "downgrade": _Example("1.3.4", "1.0.1", {"is_downgrade": True}),
    },
)
def test_is_downgrade(example: _Example) -> None:
    old_lockfile, new_lockfile, expected_diff = example.expand()
    assert _json_diff_lockfile(old_lockfile, new_lockfile) == expected_diff


def test_is_source_change() -> None:
    old: Lockfile = {
        "packages": {
            "same": {"version": "1.2.3", "source": "default"},
            "changed": {"version": "1.2.3", "source": "pypi"},
        }
    }
    new: Lockfile = {
        "packages": {
            "same": {"version": "1.2.4", "source": "default"},
            "changed": {
                "version": "1.2.3",
                "source": SourceRegistry("https://registry.example/"),
            },
        }
    }
    assert _json_diff_lockfile(old, new) == snapshot(
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


def _json_diff_path(
    left_path: Traversable, right_path: Traversable
) -> pydantic.JsonValue:
    return _json_diff_lockfile(lockfile_from(left_path), lockfile_from(right_path))


def _json_diff_lockfile(left: Lockfile, right: Lockfile) -> pydantic.JsonValue:
    return DIFF_SCHEMA.dump_python(diff(left, right), mode="json")
