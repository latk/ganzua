import pytest
from inline_snapshot import snapshot

import lockinator

from . import resources


def test_can_load_old_uv() -> None:
    lock = lockinator.lockfile_from(resources.OLD_UV_LOCKFILE)
    assert lock == snapshot(
        {
            "example": {"version": "0.1.0"},
            "typing-extensions": {"version": "3.10.0.2"},
        }
    )


def test_can_load_new_uv() -> None:
    lock = lockinator.lockfile_from(resources.NEW_UV_LOCKFILE)
    assert lock == snapshot(
        {
            "annotated-types": {"version": "0.7.0"},
            "example": {"version": "0.1.0"},
            "typing-extensions": {"version": "4.14.1"},
        }
    )


def test_cannot_load_empty_file() -> None:
    with pytest.raises(ValueError, match="unsupported lockfile format"):
        lockinator.lockfile_from(resources.EMPTY)
