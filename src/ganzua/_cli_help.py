import contextlib
import inspect
import textwrap
import typing as t
from dataclasses import dataclass

import click
import rich
import rich.console
from rich.style import Style
from rich.text import Text

_HEADING_STYLE = Style(color="green", bold=True)
_CODE_STYLE = Style(color="cyan")
_OPT_STYLE = Style(color="cyan", bold=True)


def show_help(ctx: click.Context, _param: click.Parameter, want_help: bool) -> None:
    if not want_help or ctx.resilient_parsing:
        return
    rich.print(_as_rich_group(format_command_help(ctx, recursive=False)))
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
@click.argument("subcommand", nargs=-1)
@click.pass_context
def help_command(
    help_ctx: click.Context,
    recursive: bool,
    markdown: bool,
    subcommand: tuple[str, ...],
) -> None:
    """Show help for the application or a specific subcommand."""
    ctx = help_ctx.find_root()

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
        help_items = format_command_help(ctx, recursive=recursive)
        if markdown:
            click.echo(
                "\n".join(line for item in help_items for line in _as_markdown(item))
            )
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
            rich.print(_as_rich_group(format_command_help(ctx, recursive=False)))
            ctx.exit(2)
        return super().parse_args(ctx, args)


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

    def command(self) -> t.Callable[[t.Callable], click.Command]:
        """Register a subcommand."""
        return self.click.command(cls=_FixedCommand)


type _MarkdownOrRich = (
    str
    | _Usage
    | _DefinitionList
    | _HelpHeading
    | _SubcommandHeading
    | _Markdown
    | _Indent
)


def _as_markdown(item: _MarkdownOrRich, *, level: int = 3) -> t.Iterable[str]:
    r"""Convert the help content to Markdown.

    Example: can emit headings.

    >>> doc = [
    ...     _Markdown("content"),
    ...     _SubcommandHeading("some info"),
    ...     _Markdown("more content"),
    ... ]
    >>> print("\n".join(line for item in doc for line in _as_markdown(item)))
    content
    <BLANKLINE>
    <BLANKLINE>
    ### some info
    <BLANKLINE>
    more content
    """
    match item:
        case str():
            yield item
        case _DefinitionList():
            for key, description in item.items:
                yield f"* `{key}`"
                yield textwrap.indent(description.content, "  ")
        case _Usage():
            yield f"Usage: `{item.usage}`"
        case _HelpHeading():
            yield f"**{item.text}**\n"
        case _SubcommandHeading():
            atx_prefix = "#" * level
            yield "\n"
            yield f"{atx_prefix} {item.text}"
            yield ""
        case _Markdown():
            yield item.content
        case _Indent():
            yield from _as_markdown(item.content, level=level)
        case other:  # pragma: no cover
            t.assert_never(other)


def _as_rich(  # noqa: PLR0911  # too-many-return-statement
    item: _MarkdownOrRich,
) -> rich.console.RenderableType:
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
            return rich.markdown.Markdown(item.content)
        case _Indent():
            return rich.padding.Padding(_as_rich(item.content), pad=(0, 0, 0, item.pad))
        case other:  # pragma: no cover
            t.assert_never(other)


def _as_rich_group(items: t.Iterable[_MarkdownOrRich]) -> rich.console.Group:
    return rich.console.Group(*(_as_rich(item) for item in items))


def format_command_help(
    ctx: click.Context, *, recursive: bool
) -> t.Iterable[_MarkdownOrRich]:
    """Format the command help as a Rich renderable.

    Args:
      ctx: the click-context for the current command.
      recursive: wether to also emit subcommands

    Example: can format a basic command.

    >>> cmd = click.Command(name="foo", add_help_option=False)
    >>> ctx = cmd.make_context("foo", [])
    >>> _render(format_command_help(ctx, recursive=False))
    Usage: foo [OPTIONS]
    """
    yield _Usage(ctx)

    if ctx.command.help:
        yield ""
        yield _Markdown(inspect.cleandoc(ctx.command.help))

    params = ctx.command.get_params(ctx)
    if options := [p for p in params if isinstance(p, click.Option)]:
        yield ""
        yield _HelpHeading("Options:")
        yield _Indent(
            _DefinitionList(
                [(_option_opts(opt, ctx), _Markdown(opt.help or "")) for opt in options]
            )
        )

    if isinstance(ctx.command, click.Group) and (commands := ctx.command.commands):
        yield ""
        yield _HelpHeading("Commands:")
        yield _Indent(
            _DefinitionList(
                [
                    (Text(name, style=_OPT_STYLE), _command_short_help(cmd))
                    for name, cmd in commands.items()
                ]
            )
        )

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
            yield from format_command_help(ctx_cmd, recursive=recursive)


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
    import re  # noqa: PLC0415
    from io import StringIO  # noqa: PLC0415

    if isinstance(renderable, str | Text):
        pass
    elif isinstance(renderable, t.Iterable):
        renderable = _as_rich_group(renderable)

    file = StringIO()
    rich.console.Console(width=width, file=file).print(renderable)
    print(re.sub(r"(?m) +$", "", file.getvalue().strip()))  # strip trailing space


@dataclass
class _DefinitionList:
    """A list that tries to render as a compact table, if space is available.

    Example: format depends on the key width.

    >>> dl = _DefinitionList(
    ...     [
    ...         (Text("some-key"), _Markdown("description")),
    ...         (Text("another-key"), _Markdown("another description")),
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

    items: list[tuple[Text, _Markdown]]

    def _max_key_len(self) -> int:
        """The terminal cell size of the longest key."""
        return max(key.cell_len for key, _description in self.items)

    def _should_render_nextline(self, *, max_width: int) -> bool:
        """Decide whether the definition list items should be split onto 2 lines."""
        fraction_used_by_key = self._max_key_len() / max_width
        max_key_fraction = 0.4
        return fraction_used_by_key > max_key_fraction

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        if self._should_render_nextline(max_width=options.max_width):
            for key, description in self.items:
                yield key
                yield _as_rich(_Indent(description))
            return

        import rich.table  # noqa: PLC0415  # lazy import

        table = rich.table.Table.grid(expand=True)
        table.add_column(no_wrap=True)
        table.add_column(width=2)
        table.add_column()
        for key, description in self.items:
            table.add_row(key, "", _as_rich(description))
        yield table
