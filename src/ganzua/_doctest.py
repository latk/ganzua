"""Custom doctest-style functionality."""

import html
import pathlib
import re
import shlex
import tempfile
import typing as t
from dataclasses import dataclass

import pydantic

from .cli import app


class _Line(str):
    path: pathlib.Path
    lineno: int

    def __new__(cls, value: str, *, path: pathlib.Path, lineno: int) -> t.Self:
        self = super().__new__(cls, value)
        self.path = path
        self.lineno = lineno
        return self

    def make_err(self, msg: str) -> "_SyntaxError":
        return _SyntaxError(msg, self)

    def with_data[T](self, data: T) -> "_ParsedLine[T]":
        return _ParsedLine(self, data, path=self.path, lineno=self.lineno)


class _ParsedLine[T](_Line):
    data: T

    def __new__(cls, value: str, data: T, *, path: pathlib.Path, lineno: int) -> t.Self:
        self = super().__new__(cls, value, path=path, lineno=lineno)
        self.data = data
        return self


class _SyntaxError(Exception):
    def __init__(self, message: str, line: _Line) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.add_note(f"note: at {self.line.path}:{self.line.lineno}")
        self.add_note(f"note: around here: {line}")


class Runner:
    r"""Run and update all examples in a Markdown file.

    This is implemented as a single-pass parser that processes line by line.

    By default, passes through content:

    >>> Runner.run_example("foo", "bar", "baz")
    'foo\nbar\nbaz'

    Complains when there are unknown `<!-- doctest:` directives

    >>> Runner.run_example("<!-- doctest: foo bar -->")
    Traceback (most recent call last):
    ganzua._doctest._SyntaxError: unknown directive
    note: at example:1
    note: around here: <!-- doctest: foo bar -->
    """

    def __init__(self, iter: "_Input") -> None:
        self.input = iter
        self.executed_doctest_commands: int = 0
        self.ganzua = app.testrunner()
        self.directives: t.Sequence[DoctestSyntax] = [
            CommandOutputDirective(),
            ExpectedDoctestCommandsDirective(),
            ConsoleCodeBlock(),
            CollapsibleOutputBlock(),
            DoctestCheckGanzuaDiffNotes(),
            DoctestCompareOutput(),
        ]

    @classmethod
    def run(cls, path: pathlib.Path) -> str:
        """Entrypoint intended for real use."""
        input = _Input.new_from_lines(path.read_text().rstrip().splitlines(), path=path)
        return "\n".join(cls(input).process_all_lines())

    @classmethod
    def run_example(cls, *lines: str) -> str:
        """Entrypoint intended for doctests."""
        input = _Input.new_from_lines(lines, path="example")
        return "\n".join(cls(input).process_all_lines()).strip()

    @classmethod
    def run_table_example[T](cls, *lines: str, model: type[T]) -> list[T]:
        """Entrypoint intended for doctests."""
        input = _Input.new_from_lines(lines, path="example")
        loc = next(input)
        data = [
            line.data
            for line in input.consume_table(loc, model)
            if line.data is not None
        ]
        for line in input:  # pragma: no cover
            raise line.make_err("unexpected trailing content")
        return data

    def process_all_lines(self) -> t.Iterator[str]:
        while not self.input.is_empty():
            yield from self.process_line()
        yield ""  # always end with newline

    def process_line(self) -> t.Iterator[str]:
        """Process the next line or block in the document."""
        line = next(self.input)

        for directive in self.directives:
            if m := directive.START.fullmatch(line):
                yield from directive.process(self, line.with_data(m))
                return

        if line.strip().startswith("<!-- doctest:"):
            raise line.make_err("unknown directive")

        yield line

    def emit_output_block(self, output: str) -> t.Iterator[str]:
        if output.startswith(("{", "[")):
            yield "```json"
        else:
            yield "```"
        yield output
        yield "```"

    def command_output(self, command: str, *, line: _Line) -> str:
        match shlex.split(command):
            case ["ganzua", *args]:
                return self.ganzua.output(*args, print=False).strip()
            case ["echo", *args]:  # useful for testing
                return " ".join(args)
            case _:  # pragma: no cover
                raise line.make_err(f"unsupported command: {command}")


class _PeekableIter[T]:
    """Adapt an iterator to make the next element peekable.

    >>> it = _PeekableIter([1, 2, 3, 4, 5])
    >>> next(it)
    1
    >>> it.peek()
    2
    >>> it.peek()
    2
    >>> next(it)
    2
    >>> it.peek()
    3
    >>> it.back(2)
    >>> it.back(1)
    >>> it.peek()
    1
    >>> list(it)
    [1, 2, 3, 4, 5]
    """

    def __init__(self, iterator: t.Iterable[T]) -> None:
        self._iter = iter(iterator)
        self._buffer: list[T] = []

    def __iter__(self) -> t.Self:
        return self

    def __next__(self) -> T:
        try:
            return self._buffer.pop()
        except IndexError:
            pass
        return next(self._iter)

    def back(self, value: T) -> None:
        """Un-consume an item."""
        self._buffer.append(value)

    def peek(self) -> T | None:
        """Peek at the next item, without consuming it."""
        try:
            return self._buffer[-1]
        except IndexError:
            pass

        for value in self._iter:
            self._buffer.append(value)
            return value

        return None

    def is_empty(self) -> bool:
        self.peek()
        return not self._buffer

    def next_if_eq(self, expected: T | object) -> T | None:
        """Consume the next item if it compares equal to the `expected` value.

        In Python, arbitrary objects may be compared via `__eq__`/`==`,
        so `expected` has type `object`.

        >>> it = _PeekableIter([1, 2, 3])
        >>> it.next_if_eq(2) is None
        True
        >>> next(it)
        1
        >>> it.next_if_eq(2)
        2
        >>> it.next_if_eq(2) is None
        True
        >>> next(it)
        3
        >>> it.next_if_eq(2) is None
        True
        """
        for value in self:
            if value == expected:
                return value
            self.back(value)
            break
        return None


class _Input(_PeekableIter[_Line]):
    @classmethod
    def new_from_lines(
        cls, lines: t.Iterable[str], *, path: str | pathlib.Path
    ) -> t.Self:
        path_object = pathlib.Path(path)
        return cls(
            _Line(line, path=path_object, lineno=lineno)
            for lineno, line in enumerate(lines, start=1)
        )

    def consume_blank_lines(self) -> t.Iterator[str]:
        while (line := self.next_if_eq("")) is not None:
            yield line

    def consume_until_closing(self, end: str, *, loc: _Line) -> t.Iterator[str]:
        """Consume all lines until after the `end` line."""
        for line in self:
            yield line
            if line == end:
                return
        raise loc.make_err(f"must have matching `{end}`")

    def consume_while_parsed[R](
        self, parser: t.Callable[[_Line], R | None], /
    ) -> t.Iterator[_ParsedLine[R]]:
        """Consume lines while the parser matches, attaching the output as data to the line.

        The parser matches when it returns a value other than `None`.

        >>> input = _Input.new_from_lines(["a", "", "bbb", "x y", "c"], path="example")
        >>> parser = lambda line: None if " " in line else len(line)
        >>> for line in input.consume_while_parsed(parser):
        ...     print(f"{line} - {line.data}")
        a - 1
         - 0
        bbb - 3
        >>> next(input)
        'x y'
        >>> for line in input.consume_while_parsed(parser):
        ...     print(f"{line} - {line.data}")
        c - 1
        """
        for line in self:
            mapped = parser(line)
            if mapped is None:
                self.back(line)
                break
            yield line.with_data(mapped)

    def consume_table[T](
        self, loc: _Line, model: type[T]
    ) -> t.Iterator[_ParsedLine[T | None]]:
        """Consume a GFM markdown table.

        Each line will be yielded as it is processed, with the parsed data attached.
        The parsed data is `None` for header and delimiter lines.

        Spec: https://github.github.com/gfm/#tables-extension-

        >>> Runner.run_table_example(
        ...     "context", "| col |", "|--|", "| 1.2 |", model=t.Any
        ... )
        [{'col': '1.2'}]

        >>> Runner.run_table_example("context", model=t.Any)
        Traceback (most recent call last):
        ganzua._doctest._SyntaxError: must be followed by a table
        note: at example:1
        note: around here: context

        >>> Runner.run_table_example("context", "not a header", "|--|", model=t.Any)
        Traceback (most recent call last):
        ganzua._doctest._SyntaxError: must be followed by a table
        note: at example:1
        note: around here: context

        >>> Runner.run_table_example(
        ...     "context", "| col |", "not a separator", model=t.Any
        ... )
        Traceback (most recent call last):
        ganzua._doctest._SyntaxError: must be followed by a table
        note: at example:1
        note: around here: context

        >>> Runner.run_table_example(
        ...     "context", "| col |", "|--|", "| 1 | 2 | 3 |", model=t.Any
        ... )
        Traceback (most recent call last):
        ganzua._doctest._SyntaxError: expected row with 1 cells
        note: at example:4
        note: around here: | 1 | 2 | 3 |

        >>> Runner.run_table_example(
        ...     "context", "| col |", "|--|", "| 1.2 |", model=None
        ... )
        Traceback (most recent call last):
        ganzua._doctest._SyntaxError: invalid table structure
        note: at example:1
        note: around here: context
        """
        header = self._next_table_row()
        delimiter = self._next_table_row(normalize=self._normalize_table_delimiter_cell)
        if not (
            header and delimiter and delimiter.data == tuple(["-"] * len(header.data))
        ):
            raise loc.make_err("must be followed by a table")
        yield header.with_data(None)
        yield delimiter.with_data(None)
        cols = header.data

        adapter = pydantic.TypeAdapter(model)  # type: ignore[valid-type]

        while line := self._next_table_row():
            if len(line.data) != len(cols):
                raise line.make_err(f"expected row with {len(cols)} cells")
            try:
                parsed = adapter.validate_python(
                    dict(zip(cols, line.data, strict=True))
                )
            except pydantic.ValidationError as err:
                raise loc.make_err("invalid table structure") from err
            yield line.with_data(parsed)

    def _next_table_row(
        self, *, normalize: t.Callable[[str], str] = str.strip
    ) -> _ParsedLine[tuple[str, ...]] | None:
        """Consume the next line if it looks like a table row.

        Spec: https://github.github.com/gfm/#tables-extension-

        Example: leading and trailing vertical bars are ignored.

        >>> input = _Input.new_from_lines(
        ...     ["with | trailing | bar |", "| with | leading | bar"], path="example"
        ... )
        >>> input._next_table_row().data
        ('with', 'trailing', 'bar')
        >>> input._next_table_row().data
        ('with', 'leading', 'bar')
        """
        if not (line := self.peek()) or "|" not in line:
            return None
        # leading/trailing pipes are optional and should not affect the cell count
        cells = line.strip().removeprefix("|").removesuffix("|").split("|")
        next(self)  # commit
        return line.with_data(tuple(normalize(col) for col in cells))

    @staticmethod
    def _normalize_table_delimiter_cell(cell: str) -> str:
        """Normalize the cell to `-` if it is a valid table delimiter cell.

        Spec: https://github.github.com/gfm/#delimiter-row

        >>> _Input._normalize_table_delimiter_cell(":--")
        '-'
        >>> _Input._normalize_table_delimiter_cell("something else")
        'something else'
        """
        # may have leading, trailing, or surrounding ":"
        cell = cell.removeprefix(":").removesuffix(":")
        # only hyphens are allowed
        return cell.replace("-", "") or "-"


class DoctestSyntax(t.Protocol):
    START: t.ClassVar[re.Pattern[str]]

    def process(
        self, runner: "Runner", line: _ParsedLine[re.Match[str]], /
    ) -> t.Iterator[str]: ...


class CommandOutputDirective(DoctestSyntax):
    """Replace a comment-delimited region with output from the command.

    This is useful for auto-generating Markdown sections.

    Complains when a command output region is not closed:

    >>> Runner.run_example("<!-- command output: foo -->", "ignored")
    Traceback (most recent call last):
    ganzua._doctest._SyntaxError: must have matching `<!-- command output end -->`
    note: at example:1
    note: around here: <!-- command output: foo -->
    """

    START: t.ClassVar = re.compile("<!-- command output: (.+) -->")
    END: t.ClassVar = "<!-- command output end -->"

    @t.override
    def process(
        self, runner: Runner, line: _ParsedLine[re.Match[str]]
    ) -> t.Iterator[str]:
        (command,) = line.data.groups()

        for _ in runner.input.consume_until_closing(self.END, loc=line):
            pass

        yield line
        yield ""
        yield runner.command_output(command, line=line)
        yield ""
        yield self.END


class ExpectedDoctestCommandsDirective(DoctestSyntax):
    START: t.ClassVar = re.compile("<!-- expected doctest commands: (.+) -->")

    @t.override
    def process(self, runner: Runner, _line: _Line) -> t.Iterator[str]:
        yield f"<!-- expected doctest commands: {runner.executed_doctest_commands} -->"


class ConsoleCodeBlock(DoctestSyntax):
    """A `console` code block combining `$ command` lines and output.

    Complains when a console block has no commands:

    >>> Runner.run_example("``` console", "bla bla", "```")
    Traceback (most recent call last):
    ganzua._doctest._SyntaxError: must have at least one `$ ...` command line
    note: at example:1
    note: around here: ``` console

    Complains when a console block has no closing fence:

    >>> Runner.run_example("```` console", "$ ganzua help", "```")
    Traceback (most recent call last):
    ganzua._doctest._SyntaxError: must have matching closing fence
    note: at example:1
    note: around here: ```` console
    """

    START: t.ClassVar = re.compile("(```+) *console *")
    COMMAND: t.ClassVar = re.compile("[$] (.+)")

    @t.override
    def process(
        self, runner: Runner, loc: _ParsedLine[re.Match[str]]
    ) -> t.Iterator[str]:
        (end_fence,) = loc.data.groups()
        yield loc

        has_command = False
        for line in runner.input:
            if line == end_fence:
                yield line
                return
            if m := self.COMMAND.fullmatch(line):
                has_command = True
                runner.executed_doctest_commands += 1
                yield line
                yield runner.command_output(m[1], line=line)
            elif not has_command:
                raise loc.make_err("must have at least one `$ ...` command line")
            else:
                pass  # skip existing output lines

        raise loc.make_err("must have matching closing fence")


class CollapsibleOutputBlock(DoctestSyntax):
    START: t.ClassVar = re.compile("<details><summary><code>[$] (.+)</code></summary>")
    END: t.ClassVar = "</details>"

    @t.override
    def process(
        self, runner: Runner, line: _ParsedLine[re.Match[str]], /
    ) -> t.Iterator[str]:
        (command_html_escaped,) = line.data.groups()
        for _ in runner.input.consume_until_closing(self.END, loc=line):
            pass

        yield line
        yield ""
        output = runner.command_output(html.unescape(command_html_escaped), line=line)
        yield from runner.emit_output_block(output)
        yield ""
        yield self.END


class DoctestCheckGanzuaDiffNotes(DoctestSyntax):
    START: t.ClassVar = re.compile("<!-- doctest: check ganzua diff notes -->")

    @dataclass
    class Example:
        package: str
        old: str
        new: str
        notes: str

    @t.override
    def process(self, runner: Runner, loc: _Line, /) -> t.Iterator[str]:
        yield loc
        yield from runner.input.consume_blank_lines()

        # Consume the table, but don't echo it – will be recreated later.
        examples = [
            line.data
            for line in runner.input.consume_table(loc=loc, model=self.Example)
            if line.data is not None
        ]

        with tempfile.TemporaryDirectory() as tempdir:
            old = pathlib.Path(tempdir) / "old.uv.lock.toml"
            new = pathlib.Path(tempdir) / "new.uv.lock.toml"
            old.write_text(
                example_uv_lockfile(*self._example_packages("old", examples))
            )
            new.write_text(
                example_uv_lockfile(*self._example_packages("new", examples))
            )
            diff = runner.ganzua.output("diff", old, new, "--format=markdown")
        for line in diff.splitlines():
            if line.startswith("|"):
                yield line

    def _example_packages(
        self, old_new: t.Literal["old", "new"], examples: t.Iterable[Example]
    ) -> t.Iterable["ExamplePackage"]:
        for ex in examples:
            version = ex.old if old_new == "old" else ex.new
            if version != "-":
                yield ExamplePackage(name=ex.package, version=version)


class DoctestCompareOutput(DoctestSyntax):
    """Run a list of commands and compare their output.

    Complains when there are now commands:

    >>> Runner.run_example("<!-- doctest: compare output -->", "not a command list")
    Traceback (most recent call last):
    ganzua._doctest._SyntaxError: must be followed by at least one command list item
    note: at example:1
    note: around here: <!-- doctest: compare output -->

    Creates output block if necessary:

    >>> print(
    ...     Runner.run_example(
    ...         "<!-- doctest: compare output -->",
    ...         "* `$ echo hi`",
    ...         "* `$ echo bye`",
    ...         "",
    ...         "trailing content",
    ...     )
    ... )
    <!-- doctest: compare output -->
    * `$ echo hi`
    * `$ echo bye`
    <BLANKLINE>
    <details><summary>output for the above commands</summary>
    <BLANKLINE>
    Output for:
    <BLANKLINE>
    * `$ echo hi`
    <BLANKLINE>
    ```
    hi
    ```
    <BLANKLINE>
    Output for:
    <BLANKLINE>
    * `$ echo bye`
    <BLANKLINE>
    ```
    bye
    ```
    <BLANKLINE>
    </details>
    <BLANKLINE>
    trailing content
    """

    START: t.ClassVar = re.compile("<!-- doctest: compare output -->")
    COMMAND_LIST_ITEM = re.compile("[*-] `[$] (.+)`")
    OUTPUT_START = "<details><summary>output for the above commands</summary>"
    OUTPUT_END = "</details>"

    @t.override
    def process(self, runner: Runner, loc: _Line, /) -> t.Iterator[str]:
        yield loc
        yield from runner.input.consume_blank_lines()
        commands_by_output = dict[str, list[str]]()
        yield from self.consume_command_list(runner, commands_by_output)
        if not commands_by_output:
            raise loc.make_err("must be followed by at least one command list item")

        for _ in runner.input.consume_blank_lines():
            pass
        has_existing_output_block = self.skip_output_block_if_exists(runner)

        yield ""
        yield self.OUTPUT_START
        yield ""
        for output, commands in commands_by_output.items():
            if len(commands_by_output) > 1:  # only show if ambiguous
                yield "Output for:"
                yield ""
                for command in commands:
                    yield f"* `$ {command}`"
                yield ""
            yield from runner.emit_output_block(output)
            yield ""
        yield self.OUTPUT_END
        if not has_existing_output_block:
            yield ""

    def consume_command_list(
        self, runner: Runner, commands_by_output: dict[str, list[str]]
    ) -> t.Iterator[str]:
        for line in runner.input.consume_while_parsed(self.COMMAND_LIST_ITEM.fullmatch):
            yield line
            command = line.data[1]
            output = runner.command_output(command, line=line)
            commands_by_output.setdefault(output, []).append(command)

    def skip_output_block_if_exists(self, runner: Runner) -> bool:
        if line := runner.input.next_if_eq(self.OUTPUT_START):
            for _ in runner.input.consume_until_closing(self.OUTPUT_END, loc=line):
                pass
            return True
        return False


class ExamplePackage(t.TypedDict, total=False):
    """Key information for an example package in a lockfile."""

    name: str
    version: str
    source_toml: str


def example_uv_lockfile(*packages: ExamplePackage) -> str:
    """Create example `uv.lock` file contents with the given packages."""
    default_source_toml = '{ registry = "https://pypi.org/simple" }'

    lockfile = """\
version = 1
revision = 3
requires-python = ">=3.12"
"""
    for package in packages:
        lockfile += f"""\

[[package]]
name = "{package.get("name", "example")}"
version = "{package.get("version", "0.1.0")}"
source = {package.get("source_toml", default_source_toml)}
"""

    if not packages:
        lockfile += "package = []"

    return lockfile


def example_poetry_lockfile(*packages: ExamplePackage) -> str:
    """Create example `poetry.lock` file contents with the given packages."""
    lockfile = ""
    for package in packages:
        lockfile += f"""\

[[package]]
name = "{package.get("name", "example")}"
version = "{package.get("version", "0.1.0")}"
    """
        if source_toml := package.get("source_toml"):
            lockfile += f"""\

[package.source]
{source_toml}
"""

    if not lockfile:
        lockfile = "package = []"

    return f"""\
{lockfile.strip()}

[metadata]
lock-version = "2.1"
python-versions = ">=3.12"
content-hash = "0000000000000000000000000000000000000000000000000000000000000000"
"""
