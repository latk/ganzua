import typing as t

from ._diff import Diff
from ._lockfile import LockedPackage, Lockfile
from ._requirement import Requirements


def md_from_lockfile(lockfile: Lockfile) -> str:
    """Summarize the Lockfile as a Markdown table."""
    return _table(
        ("package", "version"),
        sorted(
            (package, data["version"])
            for (package, data) in lockfile["packages"].items()
        ),
    )


def md_from_diff(diff: Diff) -> str:
    """Summarize the Diff as a Markdown table."""

    def pick_version(p: LockedPackage | None) -> str:
        if p is None:
            return "-"
        return p["version"]

    summary = f"{diff['stat']['total']} changed packages"
    if summary_details := ", ".join(_diff_summary_details(diff)):
        summary += f" ({summary_details})"

    sections: list[str] = [summary]

    if diff["stat"]["total"] > 0:
        sections.append(
            _table(
                ("package", "old", "new"),
                sorted(
                    (package, pick_version(data["old"]), pick_version(data["new"]))
                    for (package, data) in diff["packages"].items()
                ),
            )
        )

    return "\n\n".join(sections)


def _diff_summary_details(diff: Diff) -> t.Iterator[str]:
    stat = diff["stat"]
    if count := stat["added"]:
        yield f"{count} added"
    if count := stat["updated"]:
        yield f"{count} updated"
    if count := stat["removed"]:
        yield f"{count} removed"


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
