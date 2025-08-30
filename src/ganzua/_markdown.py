import typing as t
from dataclasses import dataclass

from ganzua._constraints import Requirements

from ._diff import Diff
from ._lockfile import LockedPackage, Lockfile


def md_from_lockfile(lockfile: Lockfile) -> str:
    """Summarize the Lockfile as a Markdown table."""
    return _table(
        ("package", "version"),
        sorted((package, data["version"]) for (package, data) in lockfile.items()),
    )


def md_from_diff(diff: Diff) -> str:
    """Summarize the Diff as a Markdown table."""

    def pick_version(p: LockedPackage | None) -> str:
        if p is None:
            return "-"
        return p["version"]

    stat = DiffStat.from_diff(diff)

    sections: list[str] = [stat.to_markdown()]

    if stat.total > 0:
        sections.append(
            _table(
                ("package", "old", "new"),
                sorted(
                    (package, pick_version(data["old"]), pick_version(data["new"]))
                    for (package, data) in diff.items()
                ),
            )
        )

    return "\n\n".join(sections)


@dataclass
class DiffStat:
    total: int = 0
    added: int = 0
    removed: int = 0
    updated: int = 0

    @classmethod
    def from_diff(cls, diff: Diff) -> t.Self:
        stat = cls()
        for package in diff.values():
            stat.total += 1
            if package["old"] is None:
                stat.added += 1
            elif package["new"] is None:
                stat.removed += 1
            else:
                stat.updated += 1
        return stat

    def to_markdown(self) -> str:
        details = {
            "added": self.added,
            "updated": self.updated,
            "removed": self.removed,
        }
        details_str = ", ".join(
            f"{count} {status}" for status, count in details.items() if count > 0
        )
        msg = f"{self.total} changed packages"
        if details_str:
            msg += f" ({details_str})"
        return msg


def md_from_requirements(reqs: Requirements) -> str:
    """Summarize Requirements as a Markdown table."""
    return _table(
        ("package", "version"),
        sorted((r["name"], r["specifier"]) for r in reqs["requirements"]),
    )


def _table[Row: tuple[str, ...]](header: Row, values: t.Sequence[Row]) -> str:
    """Render a Markdown table.

    Example: columns are properly aligned.

    >>> print(_table(("a", "bbb"), [("111", "2"), ("3", "4")]))
    | a   | bbb |
    |-----|-----|
    | 111 | 2   |
    | 3   | 4   |
    """
    cols = tuple(zip(header, *values, strict=True))
    col_widths = tuple(
        max((len(cell) for cell in column), default=0) for column in cols
    )
    lines = []
    lines.append("| " + " | ".join(_justify_cols(header, col_widths)) + " |")
    lines.append("|-" + "-|-".join("-" * width for width in col_widths) + "-|")
    lines.extend(
        "| " + " | ".join(_justify_cols(row, col_widths)) + " |" for row in values
    )
    return "\n".join(lines)


def _justify_cols(row: tuple[str, ...], widths: tuple[int, ...]) -> tuple[str, ...]:
    return tuple(cell.ljust(width) for cell, width in zip(row, widths, strict=True))
