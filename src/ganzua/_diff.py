import typing as t
from dataclasses import dataclass

import pydantic
from packaging.version import InvalidVersion, Version

from ._lockfile import LockedPackage, Lockfile


def _is_falsey(value: object) -> bool:
    return not value


@pydantic.with_config(use_attribute_docstrings=True)
@dataclass(kw_only=True)
class DiffEntry:
    old: LockedPackage | None
    new: LockedPackage | None

    is_major_change: t.Annotated[
        bool, pydantic.Field(default=False, exclude_if=_is_falsey)
    ]
    """True if there was a major version change.

    This doesn't literally mean "the SemVer-major version component changed",
    but is intended to highlight version changes that are likely to have breakage.
    """

    is_downgrade: t.Annotated[
        bool, pydantic.Field(default=False, exclude_if=_is_falsey)
    ]
    """True if the version was downgraded."""

    is_source_change: t.Annotated[
        bool, pydantic.Field(default=False, exclude_if=_is_falsey)
    ]
    """True if the package source changed."""


@dataclass(kw_only=True)
class DiffStat:
    total: int
    added: int
    removed: int
    updated: int


@dataclass(kw_only=True)
class Diff:
    stat: DiffStat
    packages: dict[str, DiffEntry]


def diff(old: Lockfile, new: Lockfile) -> Diff:
    """Show version changes between the two lockfiles."""
    the_diff: Diff = Diff(
        stat=DiffStat(total=0, added=0, removed=0, updated=0),
        packages={},
    )
    for package_name in sorted({*old["packages"], *new["packages"]}):
        entry = _package_diff(
            old=old["packages"].get(package_name),
            new=new["packages"].get(package_name),
        )
        if entry is None:
            continue
        the_diff.packages[package_name] = entry
        the_diff.stat.total += 1
        the_diff.stat.added += entry.old is None
        the_diff.stat.removed += entry.new is None
        the_diff.stat.updated += entry.old is not None and entry.new is not None
    return the_diff


def _package_diff(
    *, old: LockedPackage | None, new: LockedPackage | None
) -> DiffEntry | None:
    if old == new:
        return None
    return DiffEntry(
        old=old,
        new=new,
        is_major_change=_is_major_change(old, new),
        is_downgrade=_is_downgrade(old, new),
        is_source_change=_is_source_change(old, new),
    )


def _is_major_change(old: LockedPackage | None, new: LockedPackage | None) -> bool:
    # Treat adding or removing packages as safe, to reduce non-actionable alerts.
    if old is None or new is None:
        return False

    # Parse the versions.
    try:
        old_version = Version(old["version"])
    except InvalidVersion:
        old_version = None
    try:
        new_version = Version(new["version"])
    except InvalidVersion:
        new_version = None

    # If the versions are syntactically invalid, the change may be unsafe.
    if old_version is None or new_version is None:
        return True

    # Changes in Epoch or Major version are breaking.
    if old_version.epoch != new_version.epoch:
        return True
    if old_version.major != new_version.major:
        return True

    # Handle ZeroVer, where the "minor" component acts as the major version.
    if old_version.major == new_version.major == 0:
        if old_version.minor != new_version.minor:
            return True

    # All other cases should be safe.
    return False


def _is_downgrade(old: LockedPackage | None, new: LockedPackage | None) -> bool:
    if old is None or new is None:
        return False

    try:
        old_version = Version(old["version"])
        new_version = Version(new["version"])
    except InvalidVersion:
        return False

    return old_version > new_version


def _is_source_change(old: LockedPackage | None, new: LockedPackage | None) -> bool:
    if old is None or new is None:
        return False

    old_source = old["source"]
    new_source = new["source"]

    return old_source != new_source
