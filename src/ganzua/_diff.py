from dataclasses import dataclass

from ._lockfile import LockedPackage, Lockfile


@dataclass(kw_only=True)
class DiffEntry:
    old: LockedPackage | None
    new: LockedPackage | None


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
        old_package = old["packages"].get(package_name)
        new_package = new["packages"].get(package_name)
        if old_package == new_package:
            continue
        is_added: bool = old_package is None
        is_removed: bool = new_package is None
        the_diff.packages[package_name] = DiffEntry(old=old_package, new=new_package)
        the_diff.stat.total += 1
        the_diff.stat.added += is_added
        the_diff.stat.removed += is_removed
        the_diff.stat.updated += not (is_added or is_removed)
    return the_diff
