from importlib.resources.abc import Traversable

import pydantic
import pytest
from inline_snapshot import snapshot

from ganzua import diff
from ganzua._lockfile import lockfile_from
from ganzua.cli import DIFF_SCHEMA

from . import resources


@pytest.mark.parametrize("path", [resources.OLD_UV_LOCKFILE, resources.NEW_UV_LOCKFILE])
def test_comparing_self_is_empty(path: Traversable) -> None:
    assert _json_diff(path, path) == {
        "packages": {},
        "stat": {"total": 0, "added": 0, "removed": 0, "updated": 0},
    }


def test_uv() -> None:
    assert _json_diff(resources.OLD_UV_LOCKFILE, resources.NEW_UV_LOCKFILE) == snapshot(
        {
            "packages": {
                "annotated-types": {
                    "old": None,
                    "new": {"version": "0.7.0", "source": "pypi"},
                },
                "typing-extensions": {
                    "old": {"version": "3.10.0.2", "source": "pypi"},
                    "new": {"version": "4.14.1", "source": "pypi"},
                },
            },
            "stat": {"total": 2, "added": 1, "removed": 0, "updated": 1},
        }
    )


def _json_diff(left_path: Traversable, right_path: Traversable) -> pydantic.JsonValue:
    left = lockfile_from(left_path)
    right = lockfile_from(right_path)
    return DIFF_SCHEMA.dump_python(diff(left, right), mode="json")
