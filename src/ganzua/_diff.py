import dataclasses
import itertools
import typing as t

import pydantic
from packaging.version import InvalidVersion, Version

from ._lockfile import LockedPackage, LockedPackageNoMeta, LockfileByName
from ._pypi_metadata import PyPIMetadata


@pydantic.with_config(use_attribute_docstrings=True)
class DiffEntry(t.TypedDict):
    name: str
    """Name of the package being diffed.

    *Added in Ganzua 0.4.0:* previously, the package name was implicit.
    """

    old: LockedPackageNoMeta | None
    new: LockedPackageNoMeta | None

    pypi_metadata: t.NotRequired[PyPIMetadata]
    """PyPI metadata for the `new` version, if any.

    This field will only be populated if
    metadata was explicitly requested via `--pypi-metadata`,
    the package seems to have been installed from PyPI,
    and PyPI successfully provided metadata for the new version.

    *Added in Ganzua NEXT*.
    """

    is_major_change: t.NotRequired[bool]
    """True if there was a major version change.

    This doesn't literally mean "the SemVer-major version component changed",
    but is intended to highlight version changes that are likely to have breakage.
    """

    is_downgrade: t.NotRequired[bool]
    """True if the version was downgraded."""

    is_source_change: t.NotRequired[bool]
    """True if the package source changed."""

    is_yanked: t.NotRequired[bool]
    """True if the new version was yanked (per `pypi_metadata`).

    *Added in Ganzua NEXT*.
    """

    is_vulnerable: t.NotRequired[bool]
    """True if the new version has a known vulnerability (per `pypi_metadata`).

    For the purposes of this flag, withdrawn vulnerabilities are ignored.

    *Added in Ganzua NEXT*.
    """


@dataclasses.dataclass(kw_only=True)
class DiffStat:
    total: int
    added: int
    removed: int
    updated: int


@dataclasses.dataclass(kw_only=True)
class Diff:
    stat: DiffStat
    packages: list[DiffEntry]


def diff(old: LockfileByName, new: LockfileByName) -> Diff:
    """Show version changes between the two lockfiles."""
    the_diff: Diff = Diff(
        stat=DiffStat(total=0, added=0, removed=0, updated=0),
        packages=[],
    )
    for package_name in sorted({*old, *new}):
        for entry in _package_diff(
            old=old.get(package_name, []),
            new=new.get(package_name, []),
        ):
            the_diff.packages.append(entry)
            the_diff.stat.total += 1
            the_diff.stat.added += entry["old"] is None
            the_diff.stat.removed += entry["new"] is None
            the_diff.stat.updated += (
                entry["old"] is not None and entry["new"] is not None
            )
    return the_diff


def _package_diff(
    *,
    old: t.Sequence[LockedPackage],
    new: t.Sequence[LockedPackage],
) -> t.Iterator[DiffEntry]:
    """Show differences between packages of the same name."""
    name = (old or new)[0]["name"]  # we know at least one side is non-empty

    # remove common elements
    old_uniq = [p for p in old if p not in new]
    new_uniq = [p for p in new if p not in old]

    # Just do pairwise comparisons for now.
    # If either side is longer, the excess packages will be counted as added/removed,
    # all other packages will count as modified.
    # In the future, it might be possible to pair up packages more cleverly.
    for old_p, new_p in itertools.zip_longest(old_uniq, new_uniq, fillvalue=None):
        entry = DiffEntry(name=name, old=old_p, new=new_p)
        if _is_major_change(old_p, new_p):
            entry["is_major_change"] = True
        if _is_downgrade(old_p, new_p):
            entry["is_downgrade"] = True
        if _is_source_change(old_p, new_p):
            entry["is_source_change"] = True
        yield entry


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
