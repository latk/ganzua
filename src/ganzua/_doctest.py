"""Custom doctest-style functionality."""

import html
import pathlib
import re
import shlex
import typing as t
from dataclasses import dataclass

from ganzua.cli import app


class _Line(str):
    path: pathlib.Path
    lineno: int

    def __new__(cls, value: str, *, path: pathlib.Path, lineno: int) -> t.Self:
        self = super().__new__(cls, value)
        self.path = path
        self.lineno = lineno
        return self

    def raise_syntax_error(self, msg: str) -> t.Never:
        raise _SyntaxError(msg, self)


class _SyntaxError(Exception):
    def __init__(self, message: str, line: _Line) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.add_note(f"note: at {self.line.path}:{self.line.lineno}")
        self.add_note(f"note: around here: {line}")


class _PeekableIter[T]:
    """Adapt an iterator to make the next element peekable.

    >>> it = _PeekableIter(iter([1, 2, 3, 4, 5]))
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
    >>> list(it)
    [3, 4, 5]
    """

    def __init__(self, iter: t.Iterator[T]) -> None:
        self._iter = iter
        self._buffer: tuple[T] | None = None

    def __iter__(self) -> t.Self:
        return self

    def __next__(self) -> T:
        if not self._buffer:
            return next(self._iter)

        (value,) = self._buffer
        self._buffer = None
        return value

    def peek(self) -> T | None:
        if self._buffer:
            return self._buffer[0]

        for value in self._iter:
            self._buffer = (value,)
            return value
        return None

    def is_empty(self) -> bool:
        self.peek()
        return self._buffer is None


@dataclass
class Runner:
    r"""Run and update all examples in a Markdown file.

    This is implemented as a parser that processes line by line.

    By default, passes through content:

    >>> Runner.run_example("foo", "bar", "baz")
    'foo\nbar\nbaz\n'

    Complains when a command output region is not closed:

    >>> Runner.run_example("<!-- command output: foo -->", "ignored")
    Traceback (most recent call last):
    ganzua._doctest._SyntaxError: must have matching `<!-- command output end -->`
    note: at example:1
    note: around here: <!-- command output: foo -->

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

    iter: _PeekableIter[_Line]

    COMMAND_OUTPUT_START = re.compile("<!-- command output: (.+) -->")
    COMMAND_OUTPUT_END = "<!-- command output end -->"
    EXPECTED_DOCTEST_COMMANDS = re.compile(r"<!-- expected doctest commands: (\d+) -->")
    CONSOLE_BLOCK_START = re.compile("(```+) *console *")
    CONSOLE_COMMAND = re.compile("[$] (.+)")
    COLLAPSIBLE_BLOCK_START = re.compile(
        "<details><summary><code>[$] (.+)</code></summary>"
    )
    COLLAPSIBLE_BLOCK_END = "</details>"

    def __post_init__(self) -> None:
        self.executed_doctest_commands: int = 0
        self.ganzua = app.testrunner()

    @classmethod
    def new_from_lines(cls, *lines: str, path: str | pathlib.Path) -> t.Self:
        path_object = pathlib.Path(path)
        line_iter = _PeekableIter(
            _Line(line, path=path_object, lineno=lineno)
            for lineno, line in enumerate(lines, start=1)
        )
        return cls(line_iter)

    @classmethod
    def run(cls, path: pathlib.Path) -> str:
        """Entrypoint intended for real use."""
        lines = path.read_text().rstrip().splitlines()
        return cls.new_from_lines(*lines, path=path).updated()

    @classmethod
    def run_example(cls, *lines: str) -> str:
        """Entrypoint intended for doctests."""
        return cls.new_from_lines(*lines, path="example").updated()

    def updated(self) -> str:
        return "\n".join(self.process_all_lines())

    def process_all_lines(self) -> t.Iterator[str]:
        while not self.iter.is_empty():
            yield from self.process_line()
        yield ""  # always end with newline

    def process_line(self) -> t.Iterator[str]:
        """Process the next line or block in the document."""
        line = next(self.iter)

        if m := self.COMMAND_OUTPUT_START.fullmatch(line):
            self.consume_until_closing(self.COMMAND_OUTPUT_END, loc=line)

            yield line
            yield ""
            yield self.command_output(m[1], line=line)
            yield ""
            yield self.COMMAND_OUTPUT_END

        elif m := self.EXPECTED_DOCTEST_COMMANDS.fullmatch(line):
            yield f"<!-- expected doctest commands: {self.executed_doctest_commands} -->"

        elif m := self.CONSOLE_BLOCK_START.fullmatch(line):
            end_fence = m[1]
            yield line
            yield from self.process_console_block_contents(
                end_fence=end_fence, loc=line
            )
            yield end_fence

        elif m := self.COLLAPSIBLE_BLOCK_START.fullmatch(line):
            self.consume_until_closing(self.COLLAPSIBLE_BLOCK_END, loc=line)

            yield line
            yield ""
            output = self.command_output(html.unescape(m[1]), line=line)
            if output.startswith(("{", "[")):
                yield "```json"
            else:
                yield "```"
            yield output
            yield "```"
            yield ""
            yield self.COLLAPSIBLE_BLOCK_END

        else:
            yield line

    def process_console_block_contents(
        self, *, end_fence: str, loc: _Line
    ) -> t.Iterator[str]:
        """Process a console code block, excluding the first line."""
        has_command = False
        for line in self.iter:
            if line == end_fence:
                return
            if m := self.CONSOLE_COMMAND.fullmatch(line):
                has_command = True
                self.executed_doctest_commands += 1
                yield line
                yield self.command_output(m[1], line=line)
            elif not has_command:
                loc.raise_syntax_error("must have at least one `$ ...` command line")
            else:
                pass  # skip existing output lines
        loc.raise_syntax_error("must have matching closing fence")

    def consume_until_closing(self, end: str, *, loc: _Line) -> None:
        """Consume all lines until the `end` line is found."""
        for line in self.iter:
            if line == end:
                return
        loc.raise_syntax_error(f"must have matching `{end}`")

    def command_output(self, command: str, *, line: _Line) -> str:
        match shlex.split(command):
            case ["ganzua", *args]:
                return self.ganzua.output(*args, print=False).strip()
            case _:  # pragma: no cover
                line.raise_syntax_error(f"unsupported command: {command}")
