"""Content that can be printed on a console or as Markdown."""

import re
import textwrap
import typing as t
from dataclasses import dataclass

import rich.console
import rich.style
import rich.text

_HEADING_STYLE = rich.style.Style(color="green", bold=True)
_CODE_STYLE = rich.style.Style(color="cyan")
_OPT_STYLE = rich.style.Style(color="cyan", bold=True)


type AnyContent = (
    str
    | Usage
    | DefinitionList
    | HelpHeading
    | SubcommandHeading
    | Markdown
    | Indent
    | t.Sequence[AnyContent]
)


@dataclass
class Usage:
    usage: str


@dataclass
class HelpHeading:
    text: str


@dataclass
class SubcommandHeading:
    text: str


@dataclass
class Markdown:
    content: str


@dataclass
class Indent:
    content: AnyContent
    pad: int = 4


@dataclass
class DefinitionListItem:
    key: rich.text.Text
    description: AnyContent
    xref: str | None = None

    @classmethod
    def from_option(
        cls, name: str, *, description: AnyContent, xref: str | None
    ) -> t.Self:
        return cls(rich.text.Text(name, style=_OPT_STYLE), description, xref)


@dataclass
class DefinitionList:
    """A list that tries to render as a compact table, if space is available.

    Example: format depends on the key width.

    >>> dl = DefinitionList(
    ...     [
    ...         DefinitionListItem.from_option(
    ...             "some-key", description=Markdown("description"), xref=None
    ...         ),
    ...         DefinitionListItem.from_option(
    ...             "another-key",
    ...             description=Markdown("another description"),
    ...             xref=None,
    ...         ),
    ...     ]
    ... )
    >>> doctest_render(dl, width=100)
    some-key     description
    another-key  another description
    >>> doctest_render(dl, width=24)
    some-key
        description
    another-key
        another description
    """

    items: list[DefinitionListItem]

    def _max_key_len(self) -> int:
        """The terminal cell size of the longest key."""
        return max(item.key.cell_len for item in self.items)

    def _should_render_nextline(self, *, max_width: int) -> bool:
        """Decide whether the definition list items should be split onto 2 lines."""
        fraction_used_by_key = self._max_key_len() / max_width
        max_key_fraction = 0.4
        return fraction_used_by_key > max_key_fraction

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        if self._should_render_nextline(max_width=options.max_width):
            for item in self.items:
                yield item.key
                yield as_rich(Indent(item.description))
            return

        import rich.table  # noqa: PLC0415  # lazy import

        table = rich.table.Table.grid(expand=True)
        table.add_column(no_wrap=True)
        table.add_column(width=2)
        table.add_column()
        for item in self.items:
            table.add_row(item.key, "", as_rich(item.description))
        yield table


@dataclass(frozen=True, kw_only=True)
class ToMarkdownConverter:
    heading_template: str = "### {text}"
    """Used to produce the entire Markdown header line. Placeholders: `{text}`, `{slug}`."""
    link_template: str | None
    """Used to produce an URL. Placeholder: `{slug}`."""

    @classmethod
    def new_nolink(cls) -> t.Self:
        return cls(link_template=None)

    @classmethod
    def new_withlink(cls) -> t.Self:
        return cls(
            heading_template='### {text}<a id="{slug}"></a>',
            link_template="#{slug}",
        )

    def make_link(self, text: str, *, xref: str | None) -> str:
        if not xref:
            return text
        if self.link_template is None:
            return text
        link = self.link_template.format(slug=_github_slugify(xref))
        return f"[{text}]({link})"

    def make_heading(self, text: str) -> str:
        return self.heading_template.format(text=text, slug=_github_slugify(text))

    def convert(self, item: AnyContent) -> t.Iterable[str]:  # noqa: C901  # complexity
        r"""Convert the help content to Markdown.

        Example: can emit headings.

        >>> converter = ToMarkdownConverter.new_nolink()
        >>> converter.print(
        ...     Markdown("content"),
        ...     SubcommandHeading("some info"),
        ...     Markdown("more content"),
        ... )
        content
        <BLANKLINE>
        <BLANKLINE>
        ### some info
        <BLANKLINE>
        more content

        Example: can emit links to anchors.

        >>> ToMarkdownConverter.new_withlink().print(
        ...     DefinitionList(
        ...         [DefinitionListItem("key", Markdown("value"), xref="some-anchor")]
        ...     ),
        ...     SubcommandHeading("some anchor"),
        ... )
        * [`key`](#some-anchor)
          value
        <BLANKLINE>
        <BLANKLINE>
        ### some anchor<a id="some-anchor"></a>
        <BLANKLINE>

        Example: can emit Markdown links.

        >>> converter.print(Markdown("this is a [link](https://example.com/)!"))
        this is a [link](https://example.com/)!
        """
        match item:
            case str():
                yield item
            case DefinitionList():
                for dl_item in item.items:
                    key = self.make_link(f"`{dl_item.key}`", xref=dl_item.xref)
                    yield f"* {key}"
                    for block in self.convert(dl_item.description):
                        yield textwrap.indent(block, "  ")
            case Usage():
                yield f"Usage: `{item.usage}`"
            case HelpHeading():
                yield f"**{item.text}**\n"
            case SubcommandHeading():
                yield "\n"
                yield self.make_heading(item.text)
                yield ""
            case Markdown():
                yield item.content
            case Indent():
                yield from self.convert(item.content)
            case items:
                for subitem in items:
                    yield from self.convert(subitem)

    def print(self, *items: AnyContent) -> None:
        """Print one or more items as Markdown."""
        for item in items:
            print("\n".join(self.convert(item)))


def as_rich(item: AnyContent) -> rich.console.RenderableType:
    """Convert help content to Rich-printable types.

    Example: can render Markdown hyperlinks.

    >>> doctest_render(as_rich(Markdown("this is a [link](https://example.com/)!")))
    this is a link (https://example.com/)!
    """
    from rich.markdown import Markdown as RichMarkdown  # noqa: PLC0415
    from rich.padding import Padding as RichPadding  # noqa: PLC0415

    match item:
        case str():
            return rich.text.Text(item)
        case DefinitionList():
            return item
        case Usage():
            u = rich.text.Text()
            u.append("Usage: ", style=_HEADING_STYLE)
            u.append(item.usage, _CODE_STYLE)
            return u
        case HelpHeading():
            return rich.text.Text(item.text, style=_HEADING_STYLE)
        case SubcommandHeading():
            return rich.text.Text(
                "\n".join(("", item.text, "-" * len(item.text))),
                end="\n\n",
                style=_HEADING_STYLE,
            )
        case Markdown():
            return RichMarkdown(item.content, hyperlinks=False)
        case Indent():
            return RichPadding(as_rich(item.content), pad=(0, 0, 0, item.pad))
        case items:
            return rich.console.Group(*(as_rich(item) for item in items))


def text_from_options(*all_opts: str, metavar: str | None) -> rich.text.Text:
    if len(all_opts) == 1:
        joined_options = rich.text.Text(all_opts[0], style=_OPT_STYLE)
    else:
        joined_options = rich.text.Text(", ").join(
            rich.text.Text(opt, style=_OPT_STYLE) for opt in all_opts
        )

    if metavar is None:
        return joined_options
    return joined_options + rich.text.Text(f" {metavar}", style=_CODE_STYLE)


def doctest_render(
    renderable: rich.console.RenderableType | t.Iterable[AnyContent],
    *,
    width: int = 80,
) -> None:
    """Print any renderable via Rich console formatting, intended for tests."""
    from io import StringIO  # noqa: PLC0415

    if isinstance(renderable, str | rich.text.Text):
        pass
    elif isinstance(renderable, t.Iterable):
        renderable = as_rich(list(renderable))

    file = StringIO()
    rich.console.Console(width=width, file=file).print(renderable)
    print(re.sub(r"(?m) +$", "", file.getvalue().strip()))  # strip trailing space


def _github_slugify(text: str) -> str:
    """Convert the link anchor text into a slug, as per the GFM rules.

    The code here is not actually correct, but is good enough for ASCII.

    >>> _github_slugify("foo [bar]")
    'foo-bar'
    """
    text = text.lower().replace(" ", "-")
    return re.sub(r"[^\w-]+", "", text)
