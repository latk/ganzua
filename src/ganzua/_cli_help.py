import contextlib
import inspect
import os
import typing as t
from dataclasses import dataclass

import click
import rich
from rich.text import Text

from . import _cli_markup as markup

if t.TYPE_CHECKING:  # pragma: no cover
    import click.testing
    import pydantic


def show_help(ctx: click.Context, _param: click.Parameter, want_help: bool) -> None:
    if not want_help or ctx.resilient_parsing:
        return
    _print_rich_command_help(ctx)
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
    fmt = _HelpFormatter(
        command_list_style=subcommand_style,
        command_list_name="path" if subcommand_path else "subcommand",
        command_list_help="summary" if subcommand_help else "name-only",
    )

    with _subcommand_context(*subcommand, help_ctx=help_ctx) as ctx:
        help_items: list[markup.AnyContent]
        if fmt.command_list_style in ("flat", "tree"):
            help_items = [markup.DefinitionList([*fmt.command_list_item(ctx)])]
        elif recursive:
            help_items = [*fmt.full_command_help_recursive(ctx)]
        else:
            help_items = [*fmt.full_command_help(ctx)]

        if markdown:
            md = markup.ToMarkdownConverter(
                heading_template=markdown_headings,
                link_template=markdown_links,
            )
            for item in help_items:
                click.echo("\n".join(md.convert(item)))
        else:
            rich.print(markup.as_rich(help_items))


class _FixedCommand(click.Command):
    @t.override
    def get_help_option(self, ctx: click.Context) -> click.Option:
        return _HELP_OPTION


class _FixedGroup(_FixedCommand, click.Group):
    @t.override
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not args and not ctx.resilient_parsing:
            _print_rich_command_help(ctx)
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

        print: bool
        """Whether to print the command output for debugging, default `True`."""

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
        if opts.get("print", True):
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


def _print_rich_command_help(ctx: click.Context) -> None:
    content = [*_HelpFormatter.default().full_command_help(ctx)]
    rich.print(markup.as_rich(content))


@dataclass
class _HelpFormatter:
    command_list_style: t.Literal["top", "tree", "flat"]
    """Whether command lists should be nested.

    | value  | description  | example                  |
    |--------|--------------|--------------------------|
    | `top`  | no recursion | `a b c`                  |
    | `tree` | nested lists | `a {a1 a2} b {b1 b2} c`  |
    | `flat` | single flat  | list `a a1 a2 b b1 b2 c` |
    """

    command_list_name: t.Literal["subcommand", "path"]
    """Whether the names in command lists should include the full path.

    * `subcommand`: only show the subcommand name, e.g. `inspect`
    * `path`: show the entire path, e.g. `ganzua constraints inspect`
    """

    command_list_help: t.Literal["name-only", "summary"]
    """Whether to show the help summary in a command list."""

    @classmethod
    def default(cls) -> t.Self:
        return cls(
            command_list_style="top",
            command_list_name="subcommand",
            command_list_help="summary",
        )

    def full_command_help_recursive(
        self, ctx: click.Context
    ) -> t.Iterable[markup.AnyContent]:
        """Format the full help message for a command and all its subcommands."""
        yield from self.full_command_help(ctx)

        if not isinstance(ctx.command, click.Group):
            return

        for name, cmd in ctx.command.commands.items():
            with click.Context(cmd, info_name=name, parent=ctx) as ctx_cmd:
                command_path = ctx_cmd.command_path
                yield markup.SubcommandHeading(command_path)
                yield from self.full_command_help_recursive(ctx_cmd)

    def full_command_help(self, ctx: click.Context) -> t.Iterable[markup.AnyContent]:
        """Format the full help message of a single command.

        Example: can format a basic command.

        >>> cmd = click.Command(name="foo", add_help_option=False)
        >>> ctx = cmd.make_context("foo", [])
        >>> fmt = _HelpFormatter.default()
        >>> markup.doctest_render(fmt.full_command_help(ctx))
        Usage: foo [OPTIONS]
        """
        yield markup.Usage(
            " ".join([ctx.command_path, *ctx.command.collect_usage_pieces(ctx)])
        )

        if ctx.command.help:
            yield ""
            yield markup.Markdown(inspect.cleandoc(ctx.command.help))

        params = ctx.command.get_params(ctx)
        if options := [
            p for p in params if isinstance(p, click.Option) and not p.hidden
        ]:
            yield ""
            yield markup.HelpHeading("Options:")
            yield markup.Indent(
                markup.DefinitionList(
                    [
                        markup.DefinitionListItem(
                            _option_opts(opt, ctx), markup.Markdown(opt.help or "")
                        )
                        for opt in options
                    ]
                )
            )

        if subcommand_list := self.subcommand_list(ctx):
            yield ""
            yield markup.HelpHeading("Commands:")
            yield markup.Indent(subcommand_list)

        if ctx.command.epilog:
            yield ""
            yield markup.Markdown(ctx.command.epilog)

    def subcommand_list(self, ctx: click.Context) -> markup.DefinitionList | None:
        """A list of subcommands, excluding the current command."""
        commands: t.Mapping[str, click.Command] = {}
        if isinstance(ctx.command, click.Group):
            commands = ctx.command.commands
        if not commands:
            return None

        children = list[markup.DefinitionListItem]()
        for nested_name, nested_cmd in commands.items():
            with click.Context(
                nested_cmd, info_name=nested_name, parent=ctx
            ) as nested_ctx:
                children.extend(self.command_list_item(nested_ctx))
        return markup.DefinitionList(children)

    def command_list_item(
        self, ctx: click.Context
    ) -> t.Iterable[markup.DefinitionListItem]:
        """A list entry for the given command, typically just one line.

        Typically, this is a single list item. However, there might be nested items,
        or the nested commands might be flattened into multiple items.
        """
        name = ctx.info_name
        if self.command_list_name == "path":
            name = ctx.command_path
        if name is None:  # pragma: no cover
            raise ValueError("all commands must have names")

        description = list[markup.AnyContent]()
        if self.command_list_help == "summary":
            description.append(_command_short_help(ctx.command))
        if self.command_list_style == "tree":
            if children := self.subcommand_list(ctx):
                description.append(children)

        yield markup.DefinitionListItem.from_option(
            name,
            description=description,
            xref=ctx.command_path,
        )

        if self.command_list_style == "flat":
            if children := self.subcommand_list(ctx):
                yield from children.items


def _option_opts(option: click.Option, ctx: click.Context) -> Text:
    """Format the option flags into a text chunk.

    Example: Can merge negations:

    >>> opt = click.Option(["-h", "--foo/--no-foo", "--bar"], help="whatever")
    >>> markup.doctest_render(_option_opts(opt, click.Context(click.Command(None))))
    -h, --[no-]foo, --bar
    """
    all_opts = [*option.opts, *option.secondary_opts]

    # Merge --no-X prefixes, similar to what Git does
    for i, opt in enumerate(list(all_opts)):
        negated = "--no-" + opt.removeprefix("--")
        if negated in all_opts:
            all_opts[i] = "--[no-]" + opt.removeprefix("--")
            all_opts.remove(negated)

    return markup.text_from_options(
        *all_opts,
        metavar=None if option.is_flag else option.make_metavar(ctx),
    )


def _command_short_help(command: click.Command) -> markup.Markdown:
    full_help = inspect.cleandoc(command.help or "")
    short_help, _sep, _rest = full_help.partition("\n\n")
    return markup.Markdown(short_help.replace("\n", " "))


@contextlib.contextmanager
def _subcommand_context(
    *subcommand: str, help_ctx: click.Context
) -> t.Iterator[click.Context]:
    """Navigate to the correct subcommand and enter its context."""
    ctx = help_ctx.find_root()

    with contextlib.ExitStack() as stack:
        for name in subcommand:
            cmd = None
            if isinstance(ctx.command, click.Group):
                cmd = ctx.command.get_command(ctx, name)
            if cmd is None:
                help_ctx.fail(f"no such subcommand: {' '.join(subcommand)}")

            # cf https://github.com/pallets/click/blob/834e04a75c5693be55f3cd8b8d3580f74086a353/src/click/core.py#L738
            ctx = stack.enter_context(click.Context(cmd, info_name=name, parent=ctx))

        yield ctx
