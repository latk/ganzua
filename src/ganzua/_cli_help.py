import contextlib
import inspect
import os
import re
import textwrap
import typing as t
from dataclasses import dataclass

import click
import rich
import rich.console
from rich.style import Style
from rich.text import Text

if t.TYPE_CHECKING:  # pragma: no cover
    import click.testing
    import pydantic

_HEADING_STYLE = Style(color="green", bold=True)
_CODE_STYLE = Style(color="cyan")
_OPT_STYLE = Style(color="cyan", bold=True)


def show_help(ctx: click.Context, _param: click.Parameter, want_help: bool) -> None:
    if not want_help or ctx.resilient_parsing:
        return
    rich.print(
        _as_rich_group(
            format_command_help(
                ctx, recursive=False, subcommands=_SubcommandTreeSettings.default()
            )
        )
    )
    ctx.exit(0)


_HELP_OPTION = click.Option(
    ("--help",),
    type=bool,
    is_flag=True,
    expose_value=False,
    callback=show_help,
    is_eager=True,
    help="Show this help message and exit.",
)


@click.command(add_help_option=False)
@click.option(
    "--all",
    "recursive",
    type=bool,
    is_flag=True,
    flag_value=True,
    help="Also show help for all subcommands.",
)
@click.option(
    "--markdown",
    type=bool,
    is_flag=True,
    flag_value=True,
    help="Output help in Markdown format.",
)
@click.option("--markdown-links", type=str, default=None, hidden=True)
@click.option("--markdown-headings", type=str, default="### {text}", hidden=True)
@click.option(
    "--subcommand-style",
    type=click.Choice(["top", "flat", "tree"]),
    default="top",
    hidden=True,
)
@click.option(
    "--subcommand-path", type=bool, is_flag=True, flag_value=True, hidden=True
)
@click.option("--subcommand-help/--no-subcommand-help", default=True, hidden=True)
@click.argument("subcommand", nargs=-1)
@click.pass_context
def help_command(  # noqa: PLR0913  # too-many-arguments
    help_ctx: click.Context,
    recursive: bool,
    markdown: bool,
    markdown_links: str | None,
    markdown_headings: str,
    subcommand_style: t.Literal["top", "flat", "tree"],
    subcommand_path: bool,
    subcommand_help: bool,
    subcommand: tuple[str, ...],
) -> None:
    """Show help for the application or a specific subcommand."""
    ctx = help_ctx.find_root()

    subcommands = _SubcommandTreeSettings(
        style=subcommand_style,
        fullname=subcommand_path,
        showhelp=subcommand_help,
    )

    with contextlib.ExitStack() as stack:
        # Navigate to the correct subcommand
        for name in subcommand:
            if (
                not isinstance(ctx.command, click.Group)
                or (cmd := ctx.command.get_command(ctx, name)) is None
            ):
                help_ctx.fail(f"no such subcommand: {' '.join(subcommand)}")

            # cf https://github.com/pallets/click/blob/834e04a75c5693be55f3cd8b8d3580f74086a353/src/click/core.py#L738
            ctx = stack.enter_context(click.Context(cmd, info_name=name, parent=ctx))
        help_items: t.Iterable[_MarkdownOrRich]
        if subcommands.style in ("flat", "tree"):
            help_items = [subcommands.describe_full(ctx)]
        else:
            help_items = format_command_help(
                ctx, recursive=recursive, subcommands=subcommands
            )
        if markdown:
            markdown_settings = _AsMarkdownSettings(
                heading_template=markdown_headings,
                link_template=markdown_links,
            )
            for item in help_items:
                click.echo("\n".join(_as_markdown(item, markdown_settings)))
        else:
            rich.print(_as_rich_group(help_items))


class _FixedCommand(click.Command):
    @t.override
    def get_help_option(self, ctx: click.Context) -> click.Option:
        return _HELP_OPTION


class _FixedGroup(_FixedCommand, click.Group):
    @t.override
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not args and not ctx.resilient_parsing:
            rich.print(
                _as_rich_group(
                    format_command_help(
                        ctx,
                        recursive=False,
                        subcommands=_SubcommandTreeSettings.default(),
                    )
                )
            )
            ctx.exit(2)
        return super().parse_args(ctx, args)


_FixedGroup.command_class = _FixedCommand
_FixedGroup.group_class = _FixedGroup


class App:
    def __init__(self, name: str, *, help: str) -> None:
        prolog, _, epilog = help.partition("\n<!-- options -->\n")
        self.click = _FixedGroup(
            name=name,
            help=prolog.strip(),
            epilog=epilog.strip() or None,
        )
        self.click.add_command(help_command)

    def __call__(self, args: t.Sequence[str] | None = None) -> object:
        return self.click.main(args)

    def command(
        self, name: str | None = None
    ) -> t.Callable[[t.Callable], click.Command]:
        """Register a subcommand."""
        return self.click.command(name)

    def group(self) -> t.Callable[[t.Callable], click.Group]:
        """Register a sub-group."""
        return self.click.group()

    def testrunner(self) -> "AppTestRunner":
        return AppTestRunner(self)


AppTestCliArg: t.TypeAlias = str | os.PathLike[str]


@t.final
@dataclass
class AppTestRunner:
    """Invoke the app in a testing context."""

    app: App
    args: t.Sequence[AppTestCliArg] = ()

    class Opts(t.TypedDict, total=False):
        expect_exit: int
        """Which exit code to expect, default `0`."""

        catch_exceptions: bool
        """Whether to catch exceptions (other than `SystemExit`), default `True`."""

    def bind(self, *args: AppTestCliArg) -> t.Self:
        """Create new runner that prefixes the given args (partial application)."""
        return type(self)(app=self.app, args=(*self.args, *args))

    def __call__(
        self, *args: AppTestCliArg, **opts: t.Unpack[Opts]
    ) -> "click.testing.Result":
        """Run an app command."""
        import click.testing  # noqa: PLC0415  # import-outside-toplevel

        __tracebackhide__ = True
        expect_exit = opts.get("expect_exit", 0)

        result = click.testing.CliRunner().invoke(
            self.app.click,
            [os.fspath(arg) for arg in (*self.args, *args)],
            catch_exceptions=opts.get("catch_exceptions", True),
        )
        print(result.output)
        if result.exit_code != expect_exit:  # pragma: no cover
            err = AssertionError("command failed with unexpected status code")
            err.add_note(f"exited with code: {result.exit_code}")
            err.add_note(f"expected exit code: {expect_exit}")
            err.add_note(f"args: {[*self.args, *args]}")
            raise err
        return result

    def output(self, *args: AppTestCliArg, **opts: t.Unpack[Opts]) -> str:
        """Run an app command and return the visible OUTPUT."""
        __tracebackhide__ = True
        return self(*args, **opts).output

    def stdout(self, *args: AppTestCliArg, **opts: t.Unpack[Opts]) -> str:
        """Run an app command and return captured STDOUT."""
        __tracebackhide__ = True
        return self(*args, **opts).stdout

    def json(
        self, *args: AppTestCliArg, **opts: t.Unpack[Opts]
    ) -> "pydantic.JsonValue":
        """Run an app command and return captured STDOUT, parsed as JSON."""
        import json  # noqa: PLC0415  # import-outside-toplevel

        __tracebackhide__ = True
        return json.loads(self(*args, **opts).stdout)


type _MarkdownOrRich = (
    str
    | _Usage
    | _DefinitionList
    | _HelpHeading
    | _SubcommandHeading
    | _Markdown
    | _Indent
    | t.Sequence[_MarkdownOrRich]
)


@dataclass(frozen=True, kw_only=True)
class _AsMarkdownSettings:
    heading_template: str = "### {text}"
    """Used to produce the entire Markdown header line. Placeholders: `{text}`, `{slug}`."""
    link_template: str | None
    """Used to produce an URL. Placeholder: `{slug}`."""

    def make_link(self, text: str, *, xref: str | None) -> str:
        if not xref:
            return text
        if self.link_template is None:
            return text
        link = self.link_template.format(slug=xref)
        return f"[{text}]({link})"

    def make_heading(self, text: str) -> str:
        return self.heading_template.format(text=text, slug=_github_slugify(text))


def _as_markdown(  # noqa: C901  # complexity
    item: _MarkdownOrRich, settings: _AsMarkdownSettings
) -> t.Iterable[str]:
    r"""Convert the help content to Markdown.

    Example: can emit headings.

    >>> def print_markdown_doc(*items, links=False):
    ...     settings = _AsMarkdownSettings(link_template=None)
    ...     if links:
    ...         settings = _AsMarkdownSettings(
    ...             link_template="#{slug}",
    ...             heading_template='### {text}<a id="{slug}"></a>',
    ...         )
    ...     for item in items:
    ...         print("\n".join(_as_markdown(item, settings)))
    >>> print_markdown_doc(
    ...     _Markdown("content"),
    ...     _SubcommandHeading("some info"),
    ...     _Markdown("more content"),
    ... )
    content
    <BLANKLINE>
    <BLANKLINE>
    ### some info
    <BLANKLINE>
    more content

    Example: can emit links to anchors.

    >>> print_markdown_doc(
    ...     _DefinitionList(
    ...         [_DefinitionListItem("key", _Markdown("value"), xref="some-anchor")]
    ...     ),
    ...     _SubcommandHeading("some anchor"),
    ...     links=True,
    ... )
    * [`key`](#some-anchor)
      value
    <BLANKLINE>
    <BLANKLINE>
    ### some anchor<a id="some-anchor"></a>
    <BLANKLINE>

    Example: can emit Markdown links.

    >>> print_markdown_doc(_Markdown("this is a [link](https://example.com/)!"))
    this is a [link](https://example.com/)!
    """
    match item:
        case str():
            yield item
        case _DefinitionList():
            for dl_item in item.items:
                key = settings.make_link(f"`{dl_item.key}`", xref=dl_item.xref)
                yield f"* {key}"
                for block in _as_markdown(dl_item.description, settings):
                    yield textwrap.indent(block, "  ")
        case _Usage():
            yield f"Usage: `{item.usage}`"
        case _HelpHeading():
            yield f"**{item.text}**\n"
        case _SubcommandHeading():
            yield "\n"
            yield settings.make_heading(item.text)
            yield ""
        case _Markdown():
            yield item.content
        case _Indent():
            yield from _as_markdown(item.content, settings)
        case items:
            for subitem in items:
                yield from _as_markdown(subitem, settings)


def _as_rich(item: _MarkdownOrRich) -> rich.console.RenderableType:
    """Convert help content to Rich-printable types.

    Example: can render Markdown hyperlinks.

    >>> _render(_as_rich(_Markdown("this is a [link](https://example.com/)!")))
    this is a link (https://example.com/)!
    """
    import rich.markdown  # noqa: PLC0415
    import rich.padding  # noqa: PLC0415

    match item:
        case str():
            return Text(item)
        case _DefinitionList():
            return item
        case _Usage():
            u = Text()
            u.append("Usage: ", style=_HEADING_STYLE)
            u.append(item.usage, _CODE_STYLE)
            return u
        case _HelpHeading():
            return Text(item.text, style=_HEADING_STYLE)
        case _SubcommandHeading():
            return Text(
                "\n".join(("", item.text, "-" * len(item.text))),
                end="\n\n",
                style=_HEADING_STYLE,
            )
        case _Markdown():
            return rich.markdown.Markdown(item.content, hyperlinks=False)
        case _Indent():
            return rich.padding.Padding(_as_rich(item.content), pad=(0, 0, 0, item.pad))
        case items:
            return _as_rich_group(items)


def _as_rich_group(items: t.Iterable[_MarkdownOrRich]) -> rich.console.Group:
    return rich.console.Group(*(_as_rich(item) for item in items))


def format_command_help(
    ctx: click.Context, *, recursive: bool, subcommands: "_SubcommandTreeSettings"
) -> t.Iterable[_MarkdownOrRich]:
    """Format the command help as a Rich renderable.

    Args:
      ctx: the click-context for the current command.
      recursive: whether to also emit full docs subcommands
      subcommands: how to briefly summarize subcommands

    Example: can format a basic command.

    >>> cmd = click.Command(name="foo", add_help_option=False)
    >>> ctx = cmd.make_context("foo", [])
    >>> subcommands = _SubcommandTreeSettings.default()
    >>> _render(format_command_help(ctx, recursive=False, subcommands=subcommands))
    Usage: foo [OPTIONS]
    """
    yield _Usage(ctx)

    if ctx.command.help:
        yield ""
        yield _Markdown(inspect.cleandoc(ctx.command.help))

    params = ctx.command.get_params(ctx)
    if options := [p for p in params if isinstance(p, click.Option) and not p.hidden]:
        yield ""
        yield _HelpHeading("Options:")
        yield _Indent(
            _DefinitionList(
                [
                    _DefinitionListItem(
                        _option_opts(opt, ctx), _Markdown(opt.help or "")
                    )
                    for opt in options
                ]
            )
        )

    if subcommand_list := subcommands.describe_subcommands(ctx):
        yield ""
        yield _HelpHeading("Commands:")
        yield _Indent(subcommand_list)

    if ctx.command.epilog:
        yield ""
        yield _Markdown(ctx.command.epilog)

    if not recursive:
        return

    if not isinstance(ctx.command, click.Group):
        return

    for name, cmd in ctx.command.commands.items():
        with click.Context(cmd, info_name=name, parent=ctx) as ctx_cmd:
            command_path = ctx_cmd.command_path
            yield _SubcommandHeading(command_path)
            yield from format_command_help(
                ctx_cmd, recursive=recursive, subcommands=subcommands
            )


@dataclass(kw_only=True)
class _SubcommandTreeSettings:
    style: t.Literal["top", "flat", "tree"]
    fullname: bool
    showhelp: bool

    @classmethod
    def default(cls) -> t.Self:
        return cls(style="top", fullname=False, showhelp=True)

    def describe_full(self, ctx: click.Context) -> _MarkdownOrRich:
        return _DefinitionList(list(self.describe_one(ctx)))

    def describe_one(self, ctx: click.Context) -> "t.Iterable[_DefinitionListItem]":
        name = ctx.info_name
        if self.fullname:
            name = ctx.command_path
        if name is None:  # pragma: no cover
            raise ValueError("all commands must have names")

        description = list[_MarkdownOrRich]()
        if self.showhelp:
            description.append(_command_short_help(ctx.command))
        if self.style == "tree":
            if children := self.describe_subcommands(ctx):
                description.append(children)

        yield _DefinitionListItem(
            Text(name, style=_OPT_STYLE),
            description,
            xref=_github_slugify(ctx.command_path),
        )

        if self.style == "flat":
            if children := self.describe_subcommands(ctx):
                yield from children.items

    def describe_subcommands(self, ctx: click.Context) -> "_DefinitionList | None":
        commands: t.Mapping[str, click.Command] = {}
        if isinstance(ctx.command, click.Group):
            commands = ctx.command.commands
        if not commands:
            return None

        children = list[_DefinitionListItem]()
        for nested_name, nested_cmd in commands.items():
            with click.Context(
                nested_cmd, info_name=nested_name, parent=ctx
            ) as nested_ctx:
                children.extend(self.describe_one(nested_ctx))
        return _DefinitionList(children)


def _github_slugify(text: str) -> str:
    """Convert the link anchor text into a slug, as per the GFM rules.

    The code here is not actually correct, but is good enough for ASCII.

    >>> _github_slugify("foo [bar]")
    'foo-bar'
    """
    text = text.lower().replace(" ", "-")
    return re.sub(r"[^\w-]+", "", text)


class _Usage:
    def __init__(self, ctx: click.Context) -> None:
        self.usage = " ".join(
            [ctx.command_path, *ctx.command.collect_usage_pieces(ctx)]
        )


@dataclass
class _HelpHeading:
    text: str


@dataclass
class _SubcommandHeading:
    text: str


@dataclass
class _Markdown:
    content: str


@dataclass
class _Indent:
    content: _MarkdownOrRich
    pad: int = 4


def _option_opts(option: click.Option, ctx: click.Context) -> Text:
    """Format the option flags into a text chunk.

    Example: Can merge negations:

    >>> opt = click.Option(["-h", "--foo/--no-foo", "--bar"], help="whatever")
    >>> _render(_option_opts(opt, click.Context(click.Command(None))))
    -h, --[no-]foo, --bar
    """
    all_opts = [*option.opts, *option.secondary_opts]

    # Merge --no-X prefixes, similar to what Git does
    for i, opt in enumerate(list(all_opts)):
        negated = "--no-" + opt.removeprefix("--")
        if negated in all_opts:
            all_opts[i] = "--[no-]" + opt.removeprefix("--")
            all_opts.remove(negated)

    if len(all_opts) == 1:
        joined_options = Text(all_opts[0], style=_OPT_STYLE)
    else:
        joined_options = Text(", ").join(
            Text(opt, style=_OPT_STYLE) for opt in all_opts
        )

    if option.is_flag:
        return joined_options
    return joined_options + Text(f" {option.make_metavar(ctx)}", style=_CODE_STYLE)


def _command_short_help(command: click.Command) -> _Markdown:
    full_help = inspect.cleandoc(command.help or "")
    short_help, _sep, _rest = full_help.partition("\n\n")
    return _Markdown(short_help.replace("\n", " "))


def _render(
    renderable: rich.console.RenderableType | t.Iterable[_MarkdownOrRich],
    *,
    width: int = 80,
) -> None:
    from io import StringIO  # noqa: PLC0415

    if isinstance(renderable, str | Text):
        pass
    elif isinstance(renderable, t.Iterable):
        renderable = _as_rich_group(renderable)

    file = StringIO()
    rich.console.Console(width=width, file=file).print(renderable)
    print(re.sub(r"(?m) +$", "", file.getvalue().strip()))  # strip trailing space


@dataclass
class _DefinitionListItem:
    key: Text
    description: _MarkdownOrRich
    xref: str | None = None


@dataclass
class _DefinitionList:
    """A list that tries to render as a compact table, if space is available.

    Example: format depends on the key width.

    >>> dl = _DefinitionList(
    ...     [
    ...         _DefinitionListItem(Text("some-key"), _Markdown("description")),
    ...         _DefinitionListItem(
    ...             Text("another-key"), _Markdown("another description")
    ...         ),
    ...     ]
    ... )
    >>> _render(dl, width=100)
    some-key     description
    another-key  another description
    >>> _render(dl, width=24)
    some-key
        description
    another-key
        another description
    """

    items: list[_DefinitionListItem]

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
                yield _as_rich(_Indent(item.description))
            return

        import rich.table  # noqa: PLC0415  # lazy import

        table = rich.table.Table.grid(expand=True)
        table.add_column(no_wrap=True)
        table.add_column(width=2)
        table.add_column()
        for item in self.items:
            table.add_row(item.key, "", _as_rich(item.description))
        yield table
