import contextlib
import inspect
import typing as t
from dataclasses import dataclass

import click
import rich
from rich.console import Console, ConsoleOptions, RenderableType, RenderResult, group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.style import Style
from rich.table import Table
from rich.text import Text

_HEADING_STYLE = Style(color="green", bold=True)
_CODE_STYLE = Style(color="cyan")
_OPT_STYLE = Style(color="cyan", bold=True)


def show_help(ctx: click.Context, _param: click.Parameter, want_help: bool) -> None:
    if not want_help or ctx.resilient_parsing:
        return
    rich.print(format_command_help(ctx, recursive=False))
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
    help="Whether to also show all subcommands.",
)
@click.argument("subcommand", nargs=-1)
@click.pass_context
def help_command(
    help_ctx: click.Context, recursive: bool, subcommand: tuple[str, ...]
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
        rich.print(format_command_help(ctx, recursive=recursive))


class _FixedCommand(click.Command):
    @t.override
    def get_help_option(self, ctx: click.Context) -> click.Option:
        return _HELP_OPTION


class _FixedGroup(_FixedCommand, click.Group):
    @t.override
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not args and not ctx.resilient_parsing:
            rich.print(format_command_help(ctx, recursive=False))
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


@group()
def format_command_help(ctx: click.Context, *, recursive: bool) -> RenderResult:
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
    yield _usage(ctx)

    if ctx.command.help:
        yield Text()
        yield Markdown(inspect.cleandoc(ctx.command.help))

    params = ctx.command.get_params(ctx)
    if options := [p for p in params if isinstance(p, click.Option)]:
        yield Text()
        yield Text("Options:", style=_HEADING_STYLE)
        yield _indent(
            _DefinitionList(
                [(_option_opts(opt), Markdown(opt.help or "")) for opt in options]
            )
        )

    if isinstance(ctx.command, click.Group) and (commands := ctx.command.commands):
        yield Text()
        yield Text("Commands:", style=_HEADING_STYLE)
        yield _indent(
            _DefinitionList(
                [
                    (Text(name, style=_OPT_STYLE), _command_short_help(cmd))
                    for name, cmd in commands.items()
                ]
            )
        )

    if ctx.command.epilog:
        yield Text()
        yield Markdown(ctx.command.epilog)

    if not recursive:
        return

    if not isinstance(ctx.command, click.Group):
        return

    for name, cmd in ctx.command.commands.items():
        with click.Context(cmd, info_name=name, parent=ctx) as ctx_cmd:
            command_path = ctx_cmd.command_path
            yield Text(end="\n\n")
            yield Text(command_path, style=_HEADING_STYLE)
            yield Text("-" * len(command_path), style=_HEADING_STYLE, end="\n\n")
            yield format_command_help(ctx_cmd, recursive=recursive)


def _usage(ctx: click.Context) -> Text:
    usage = Text()
    usage.append("Usage: ", style=_HEADING_STYLE)
    usage.append(ctx.command_path + " ", style=_CODE_STYLE)
    usage.append(" ".join(ctx.command.collect_usage_pieces(ctx)), style=_CODE_STYLE)
    return usage


def _option_opts(option: click.Option) -> Text:
    """Format the option flags into a text chunk.

    Example: Can merge negations:

    >>> opt = click.Option(["-h", "--foo/--no-foo", "--bar"], help="whatever")
    >>> _render(_option_opts(opt))
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
        return Text(all_opts[0], style=_OPT_STYLE)
    return Text(", ").join(Text(opt, style=_OPT_STYLE) for opt in all_opts)


def _command_short_help(command: click.Command) -> Markdown:
    full_help = inspect.cleandoc(command.help or "")
    short_help, _sep, _rest = full_help.partition("\n\n")
    return Markdown(short_help.replace("\n", " "))


def _render(renderable: RenderableType, *, width: int = 80) -> None:
    import re  # noqa: PLC0415
    from io import StringIO  # noqa: PLC0415

    file = StringIO()
    Console(width=width, file=file).print(renderable)
    print(re.sub(r"(?m) +$", "", file.getvalue().strip()))  # strip trailing space


@dataclass
class _DefinitionList:
    """A list that tries to render as a compact table, if space is available.

    Example: format depends on the key width.

    >>> dl = _DefinitionList(
    ...     [
    ...         (Text("some-key"), Markdown("description")),
    ...         (Text("another-key"), Markdown("another description")),
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

    items: list[tuple[Text, Markdown]]

    def as_table(self) -> Table:
        table = Table.grid(expand=True)
        table.add_column(no_wrap=True)
        table.add_column(width=2)
        table.add_column()
        for key, description in self.items:
            table.add_row(key, "", description)
        return table

    def as_list(self) -> RenderResult:
        for key, description in self.items:
            yield key
            yield _indent(description)

    def _max_key_len(self) -> int:
        """The terminal cell size of the longest key."""
        return max(key.cell_len for key, _description in self.items)

    def _should_render_nextline(self, *, max_width: int) -> bool:
        """Decide whether the definition list items should be split onto 2 lines."""
        fraction_used_by_key = self._max_key_len() / max_width
        max_key_fraction = 0.4
        return fraction_used_by_key > max_key_fraction

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        if self._should_render_nextline(max_width=options.max_width):
            yield from self.as_list()
        else:
            yield self.as_table()


def _indent(renderable: RenderableType, pad: int = 4) -> Padding:
    return Padding(renderable, pad=(0, 0, 0, pad))
