import re
import string
import typing as t
import unicodedata
from dataclasses import dataclass

import click

from ._lockfile import Lockfile


class _FilterParamType(click.ParamType):
    name = "filter"

    @t.override
    def convert(
        self, value: object, param: click.Parameter | None, ctx: click.Context | None
    ) -> "Filter":
        if isinstance(value, Filter):
            return value
        if not isinstance(value, str):  # pragma: no cover
            self.fail(f"filter must be a string: {value!r}", param, ctx)
        try:
            return Filter.compile(value)
        except _FilterSyntaxError as ex:
            self.fail(f"{ex}", param, ctx)


@dataclass
class _Pattern:
    regex: re.Pattern[str]
    negated: bool


@dataclass
class Filter:
    patterns: t.Sequence[_Pattern]
    has_positive_pattern: bool

    PARAM_TYPE: t.ClassVar = _FilterParamType()
    DEFAULT: t.ClassVar  # initialized later

    @classmethod
    def compile(cls, value: str) -> t.Self:
        patterns = _parse_all_patterns(value)
        return cls(patterns, has_positive_pattern=any(not p.negated for p in patterns))

    def matches(self, value: str) -> bool:
        # If there's a positive pattern, the default is FALSE,
        # and at least one positive pattern must match.
        # Otherwise, the default is TRUE,
        # and negative patterns may exclude the value.
        matches = not self.has_positive_pattern

        for pat in self.patterns:
            if pat.regex.fullmatch(value):
                matches = not pat.negated

        return matches


Filter.DEFAULT = Filter((), has_positive_pattern=False)


def filter_lockfile(lockfile: Lockfile, *, name_filter: Filter) -> Lockfile:
    return {
        "packages": [p for p in lockfile["packages"] if name_filter.matches(p["name"])]
    }


_PATTERN_LITERAL_FRAGMENT = re.compile(r"[a-zA-Z0-9._-]++")


def _parse_all_patterns(data: str) -> list[_Pattern]:
    i = 0
    n = len(data)
    patterns: list[_Pattern] = []
    while True:
        i = _skip_ws(data, i)
        pat, i = _parse_pattern(data, i)
        patterns.append(pat)
        i = _skip_ws(data, i)
        if i >= n:
            break
        if data[i] == ",":
            i += 1
            continue
        # left over content is a syntax error
        raise _FilterSyntaxError(
            "unexpected content after filter pattern", data=data, i=i
        )

    return patterns


def _parse_pattern(data: str, i: int) -> tuple[_Pattern, int]:
    n = len(data)

    negated = False
    if i < n and data[i] == "!":
        negated = True
        i += 1

    buf: list[str] = []
    while i < n:
        # scan literal package name parts and normalize as per spec at
        # <https://packaging.python.org/en/latest/specifications/name-normalization/>
        if m := _PATTERN_LITERAL_FRAGMENT.match(data, i):
            i = m.end()
            buf.append(re.sub(r"[-_.]+", "-", m[0]).lower())
            continue

        # wildcards
        if data[i] == "*":
            i += 1
            buf.append(".*")
            continue
        if data[i] == "?":
            i += 1
            buf.append(".")
            continue

        # explicitly warn about unsupported syntax
        if data[i] in "[]":
            raise _FilterSyntaxError(
                "bracket expressions not supported", data=data, i=i
            )
        if data[i] in "{}":
            raise _FilterSyntaxError("brace expansion not supported", data=data, i=i)

        break

    if not buf:
        raise _FilterSyntaxError("expected filter pattern", data=data, i=i)

    pattern = _Pattern(re.compile("".join(buf)), negated=negated)
    return pattern, i


def _skip_ws(data: str, i: int) -> int:
    n = len(data)
    while i < n and data[i].isspace():
        i += 1
    return i


class _FilterSyntaxError(Exception):
    def __init__(self, msg: str, *, data: str, i: int) -> None:
        super().__init__(msg)
        self.msg = msg
        self.data = data
        self.i = i

    def __str__(self) -> str:
        r"""Format the exception with a pointer to the location where the error occurred.

        Examples for the pointer:

        >>> text = "0123456789" * 10
        >>> print(_FilterSyntaxError("oops", data=text, i=3))
        oops
        at offset 3 (char '3' U+0033 DIGIT THREE):
          |012345678901234567890123456789012345678901234567890123456789012345678901234…
          |   ^
        >>> print(_FilterSyntaxError("oops", data=text, i=30))
        oops
        at offset 30 (char '0' U+0030 DIGIT ZERO):
          |012345678901234567890123456789012345678901234567890123456789012345678901234…
          |                              ^
        >>> print(_FilterSyntaxError("oops", data=text, i=31))
        oops
        at offset 31 (char '1' U+0031 DIGIT ONE):
          |…23456789012345678901234567890123456789012345678901234567890123456789012345…
          |                              ^
        >>> print(_FilterSyntaxError("oops", data=text, i=95))
        oops
        at offset 95 (char '5' U+0035 DIGIT FIVE):
          |…6789012345678901234567890123456789
          |                              ^

        Examples for control character redactions:

        >>> text = "foo\N{ESCAPE}[\n\N{RIGHT-TO-LEFT OVERRIDE}bar"
        >>> print(_FilterSyntaxError("oops", data=text, i=3))
        oops
        at offset 3 (char '\x1b' U+001B <unnamed>):
          |foo�[ �bar
          |   ^

        Examples for EOF:
        >>> print(_FilterSyntaxError("oops", data="abc", i=3))
        oops
        at offset 3 (EOF):
          |abc
          |   ^
        """
        plain = _make_safe_to_print_as_single_line(self.data)
        plain, offset = _truncate_context(plain, self.i)

        if 0 <= self.i < len(self.data):
            char = self.data[self.i]
            # The `unicodedata` module doesn't return aliases for unnamed characters.
            # E.g. the ESCAPE codepoint has no name.
            # <https://github.com/python/cpython/issues/71683>
            unicode_name = unicodedata.name(char, "<unnamed>")
            description = f"char {char!r} U+{ord(char):04X} {unicode_name}"
        else:
            description = "EOF"

        return f"""\
{self.msg}
at offset {self.i} ({description}):
  |{plain}
  |{"":{offset}}^\
"""


def _truncate_context(
    line: str, offset: int, *, max_left: int = 30, max_total: int = 76
) -> tuple[str, int]:
    """Truncate a line to focus around the `offset`."""
    if offset > max_left:
        line = "…" + line[offset - max_left + 1 :]
        offset = max_left
    if len(line) > max_total:
        line = line[: max_total - 1] + "…"
    return line, offset


def _make_safe_to_print_as_single_line(
    s: str, replacement: str = "\N{REPLACEMENT CHARACTER}"
) -> str:
    # make all spaces the same width
    s = re.sub(r"\s", " ", s)
    # redact control characters
    return "".join(replacement if _is_control_character(c) else c for c in s)


def _is_control_character(c: str) -> bool:
    if c.isascii():  # fast path
        return c not in string.printable

    # Unicode is present – check the Unicode database instead of hardcoding ranges.
    return unicodedata.category(c) in (
        "Cc",  # general control characters, e.g. C0 and C1 ranges
        "Cf",  # format characters, such as bidi control
        "Cs",  # surrogates
        "Co",  # private use
        "Cn",  # unassigned
    )
