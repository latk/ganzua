import typing as t
from dataclasses import dataclass

from ._diff import Diff, DiffEntry
from ._lockfile import LockedPackage, Lockfile
from ._package_source import Source, SourceDirect, SourceRegistry
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


class _MdDiffRow(t.NamedTuple):
    package: str
    old: str
    new: str
    notes: t.Sequence["_NoteRef"]

    def render_notes(self) -> str:
        return " ".join(n.resolved_id() for n in self.notes)


@dataclass
class _NotesRegistry:
    msgs_by_category: dict[str, list[str]]

    def register(self, category: str, msg: str) -> "_NoteRef":
        """Register a new message, returning a Ref to later find its ID."""
        msgs = self.msgs_by_category.setdefault(category, [])
        try:
            index = msgs.index(msg)
        except ValueError:  # not found
            index = len(msgs)
            msgs.append(msg)
        return _NoteRef(self, category=category, index=index)

    def items(self) -> t.Iterable[tuple["_NoteRef", str]]:
        """Get all registered `(ref, message)` pairs."""
        for category, msgs in self.msgs_by_category.items():
            for index, msg in enumerate(msgs):
                yield _NoteRef(self, category=category, index=index), msg


@dataclass
class _NoteRef:
    registry: _NotesRegistry
    category: str
    index: int

    def resolved_id(self) -> str:
        msgs = self.registry.msgs_by_category[self.category]
        if len(msgs) == 1:
            return f"({self.category})"
        return f"({self.category}{self.index + 1})"


@dataclass
class _DiffTable:
    rows: list[_MdDiffRow]
    footnotes: _NotesRegistry

    def add(self, package: str, data: DiffEntry) -> None:
        def pick_version(p: LockedPackage | None) -> str:
            if p is None:
                return "-"
            return p["version"]

        def pick_footnotes(data: DiffEntry) -> t.Iterable[_NoteRef]:
            if data.is_major_change:
                yield self.footnotes.register("M", "major change")
            if data.is_downgrade:
                yield self.footnotes.register("D", "downgrade")
            if data.is_source_change:
                if data.old is None or data.new is None:  # pragma: no cover
                    raise AssertionError(f"unexpected source change: {data}")

                old_source = md_from_source(data.old["source"])
                new_source = md_from_source(data.new["source"])
                yield self.footnotes.register(
                    "S", f"source changed from {old_source} to {new_source}"
                )

        self.rows.append(
            _MdDiffRow(
                package,
                pick_version(data.old),
                pick_version(data.new),
                list(pick_footnotes(data)),
            )
        )

    def render(self) -> t.Iterable[str]:
        yield _table(
            ("package", "old", "new", "notes"),
            [
                (row.package, row.old, row.new, row.render_notes())
                for row in sorted(self.rows)
            ],
            collapsible_cols=("notes",),
        )
        if footnotes := "\n".join(
            f"* {ref.resolved_id()} {message}"
            for ref, message in self.footnotes.items()
        ):
            yield footnotes


def md_from_diff(diff: Diff) -> str:
    """Summarize the Diff as a Markdown table."""
    summary = f"{diff.stat.total} changed packages"
    if summary_details := ", ".join(_diff_summary_details(diff)):
        summary += f" ({summary_details})"

    if diff.stat.total <= 0:
        return summary

    table = _DiffTable(rows=[], footnotes=_NotesRegistry({}))

    for package, data in diff.packages.items():
        table.add(package, data)

    sections: list[str] = [summary]
    sections.extend(table.render())

    return "\n\n".join(sections)


def md_from_source(source: Source) -> str:
    match source:
        case "pypi" | "default" | "other":
            return source
        case SourceRegistry(registry=url):
            return f"registry <{url}>"
        case SourceDirect(direct=url, subdirectory=subdir) if subdir is not None:
            return f"<{url}> (subdirectory: `{subdir}`)"
        case SourceDirect(direct=url):
            return f"<{url}>"
        case other:  # pragma: no cover
            t.assert_never(other)


def _diff_summary_details(diff: Diff) -> t.Iterator[str]:
    stat = diff.stat
    if count := stat.added:
        yield f"{count} added"
    if count := stat.updated:
        yield f"{count} updated"
    if count := stat.removed:
        yield f"{count} removed"


def md_from_requirements(reqs: Requirements) -> str:
    """Summarize Requirements as a Markdown table."""
    return _table(
        ("package", "version"),
        sorted((r["name"], r["specifier"]) for r in reqs["requirements"]),
    )


def _table[Row: tuple[str, ...]](
    header: Row,
    values: t.Sequence[Row],
    *,
    collapsible_cols: t.Container[str] = (),
) -> str:
    """Render a Markdown table.

    Example: columns are properly aligned.

    >>> print(_table(("a", "bbb"), [("111", "2"), ("3", "4")]))
    | a   | bbb |
    |-----|-----|
    | 111 | 2   |
    | 3   | 4   |

    Example: drop empty columns.

    >>> print(
    ...     _table(
    ...         ("a", "b", "c"),
    ...         [("a1", "", "c1"), ("a2", "", "c2")],
    ...         collapsible_cols=("a", "b", "c"),
    ...     )
    ... )
    | a  | c  |
    |----|----|
    | a1 | c1 |
    | a2 | c2 |
    """
    col_widths_or_empty = tuple(
        _col_width(col_name, col_values, collapsible=(col_name in collapsible_cols))
        for col_name, col_values in zip(header, zip(*values, strict=True), strict=True)
    )

    def select_cols_with_data(row: Row) -> tuple[str, ...]:
        return tuple(
            cell
            for cell, width in zip(row, col_widths_or_empty, strict=True)
            if width is not None
        )

    if any(width is None for width in col_widths_or_empty):
        return _table(
            select_cols_with_data(header),
            [select_cols_with_data(row) for row in values],
            collapsible_cols=(),
        )

    col_widths = tuple(width or 0 for width in col_widths_or_empty)

    lines = []
    lines.append("| " + " | ".join(_justify_cols(header, col_widths)) + " |")
    lines.append("|-" + "-|-".join("-" * width for width in col_widths) + "-|")
    lines.extend(
        "| " + " | ".join(_justify_cols(row, col_widths)) + " |" for row in values
    )
    return "\n".join(lines)


def _col_width(
    col_name: str, col_values: t.Iterable[str], *, collapsible: bool
) -> int | None:
    """Determine the width of a column, in characters.

    If `collapsible`, returns `None` when all values are empty.
    """
    values_width = max((len(cell) for cell in col_values), default=0)
    if collapsible and values_width == 0:
        return None
    return max(len(col_name), values_width)


def _justify_cols(row: tuple[str, ...], widths: tuple[int, ...]) -> tuple[str, ...]:
    return tuple(cell.ljust(width) for cell, width in zip(row, widths, strict=True))
