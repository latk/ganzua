import typing as t

import pydantic

from ._lockfile import LockedPackage, Lockfile


class DiffEntry(t.TypedDict):
    old: LockedPackage | None
    new: LockedPackage | None


type Diff = dict[str, DiffEntry]

DIFF_SCHEMA = pydantic.TypeAdapter[Diff](Diff)


def diff(old: Lockfile, new: Lockfile) -> Diff:
    """Show version changes between the two lockfiles."""
    the_diff: Diff = {}
    for package in sorted({*old, *new}):
        old_version = old.get(package)
        new_version = new.get(package)
        if old_version == new_version:
            continue
        the_diff[package] = DiffEntry(old=old_version, new=new_version)
    return the_diff
