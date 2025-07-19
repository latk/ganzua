from importlib.resources.abc import Traversable

import pytest
from inline_snapshot import snapshot

from lockinator import diff
from lockinator._lockfile import lockfile_from

from . import resources


@pytest.mark.parametrize("path", [resources.OLD_UV_LOCKFILE, resources.NEW_UV_LOCKFILE])
def test_comparing_self_is_empty(path: Traversable) -> None:
    assert diff(lockfile_from(path), lockfile_from(path)) == {}


def test_uv() -> None:
    old = lockfile_from(resources.OLD_UV_LOCKFILE)
    new = lockfile_from(resources.NEW_UV_LOCKFILE)
    assert diff(old, new) == snapshot(
        {
            "annotated-types": {"old": None, "new": "0.7.0"},
            "typing-extensions": {"old": "3.10.0.2", "new": "4.14.1"},
        }
    )
