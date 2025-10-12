from importlib.resources.abc import Traversable

import pytest
from inline_snapshot import snapshot

from ganzua import diff
from ganzua._lockfile import lockfile_from

from . import resources


@pytest.mark.parametrize("path", [resources.OLD_UV_LOCKFILE, resources.NEW_UV_LOCKFILE])
def test_comparing_self_is_empty(path: Traversable) -> None:
    assert diff(lockfile_from(path), lockfile_from(path)) == {
        "packages": {},
        "stat": {"total": 0, "added": 0, "removed": 0, "updated": 0},
    }


def test_uv() -> None:
    old = lockfile_from(resources.OLD_UV_LOCKFILE)
    new = lockfile_from(resources.NEW_UV_LOCKFILE)
    assert diff(old, new) == snapshot(
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
