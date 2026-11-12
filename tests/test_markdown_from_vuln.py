import typing as t

from inline_snapshot import snapshot

from ganzua._markdown import MarkdownRenderer
from ganzua._pypi_metadata import Vulnerability


def _render(**vuln: t.Unpack[Vulnerability]) -> str:
    return MarkdownRenderer(show_links=False).md_from_vuln(vuln)


def test_minimal() -> None:
    assert _render(source="osv", id="EXAMPLE") == snapshot("EXAMPLE")


def test_full() -> None:
    assert _render(
        source="osv",
        id="EXAMPLE",
        link="https://example.com",
        withdrawn="2026-11-11 11:11:11Z",
        summary="brief description",
        details="detailed description\n\n- with\n- multiple\n- paragraphs",
        aliases=["ALIAS-1", "ALIAS-2"],
        fixed_in=["1.2.3", "4.5.6"],
    ) == snapshot("""\
[EXAMPLE](https://example.com) (WITHDRAWN) brief description

  <details><summary>Details</summary>

  detailed description

  - with
  - multiple
  - paragraphs

  </details>

  Aliases: ALIAS-1, ALIAS-2

  Fixed in: 1.2.3, 4.5.6\
""")
