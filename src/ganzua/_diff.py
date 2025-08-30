import typing as t

import pydantic

from ._lockfile import LockedPackage, Lockfile


class DiffEntry(t.TypedDict):
    old: LockedPackage | None
    new: LockedPackage | None


class DiffStat(t.TypedDict):
    total: int
    added: int
    removed: int
    updated: int


class Diff(t.TypedDict):
    packages: dict[str, DiffEntry]
    stat: DiffStat


DIFF_SCHEMA = pydantic.TypeAdapter[Diff](Diff)


def diff(old: Lockfile, new: Lockfile) -> Diff:
    """Show version changes between the two lockfiles."""
    the_diff: Diff = {
        "stat": DiffStat(total=0, added=0, removed=0, updated=0),
        "packages": {},
    }
    for package in sorted({*old, *new}):
        old_version = old.get(package)
        new_version = new.get(package)
        if old_version == new_version:
            continue
        is_added: bool = old_version is None
        is_removed: bool = new_version is None
        the_diff["packages"][package] = DiffEntry(old=old_version, new=new_version)
        the_diff["stat"]["total"] += 1
        the_diff["stat"]["added"] += is_added
        the_diff["stat"]["removed"] += is_removed
        the_diff["stat"]["updated"] += not (is_added or is_removed)
    return the_diff
