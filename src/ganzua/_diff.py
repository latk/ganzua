import typing as t

import pydantic

from ._lockfile import Lockfile


class DiffEntry(t.TypedDict):
    old: str | None
    new: str | None


type Diff = dict[str, DiffEntry]

DIFF_SCHEMA = pydantic.TypeAdapter[Diff](Diff)


def diff(old: Lockfile, new: Lockfile) -> Diff:
    """Show version changes between the two lockfiles."""
    the_diff: Diff = {}
    for package in sorted({*old, *new}):
        old_version = _get_version(old, package)
        new_version = _get_version(new, package)
        if old_version == new_version:
            continue
        the_diff[package] = DiffEntry(old=old_version, new=new_version)
    return the_diff


def _get_version(lockfile: Lockfile, package: str) -> str | None:
    if not (locked_package := lockfile.get(package)):
        return None
    return locked_package["version"]
