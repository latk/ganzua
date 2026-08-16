import re
import string
import typing as t
import unicodedata
from dataclasses import dataclass

import click

from ._lockfile import Lockfile
from ._requirement import Requirement


@dataclass
class _FilterParamType[F: ("ConstraintFilter", "LockfileFilter")](click.ParamType):
    name: str
    cls: type[F]

    @t.override
    def convert(
        self, value: object, param: click.Parameter | None, ctx: click.Context | None
    ) -> F:
        if isinstance(value, self.cls):  # pragma: no cover
            return value
        if not isinstance(value, str):  # pragma: no cover
            self.fail(f"filter must be a string: {value!r}", param, ctx)
        try:
            return self.cls.compile(value)
        except _FilterSyntaxError as ex:
            self.fail(f"{ex}", param, ctx)


@dataclass
class ConstraintFilter:
    rules: t.Sequence["Rule"]
    has_positive_pattern: bool

    PARAM_TYPE: t.ClassVar[_FilterParamType[t.Any]]  # initialized later
    DEFAULT: t.ClassVar[t.Self]  # initialized later

    @dataclass(kw_only=True)
    class Rule:
        negated: bool
        name: re.Pattern[str] | None
        extra: re.Pattern[str] | None
        group: re.Pattern[str] | None

        def matches(self, req: Requirement) -> bool:
            if self.name:
                if not self.name.fullmatch(req["name"]):
                    return False
            if self.extra:
                if not any(
                    self.extra.fullmatch(extra) for extra in req.get("in_extras", ())
                ):
                    return False
            if self.group:
                if not any(
                    self.group.fullmatch(group) for group in req.get("in_groups", ())
                ):
                    return False
            return True

    @classmethod
    def compile(cls, value: str) -> t.Self:
        rules = _parse_all_rules(value, rule_type=cls.Rule)
        return cls(rules, has_positive_pattern=any(not p.negated for p in rules))

    def matches(self, req: Requirement) -> bool:
        # If there's a positive pattern, the default is FALSE,
        # and at least one positive pattern must match.
        # Otherwise, the default is TRUE,
        # and negative patterns may exclude the value.
        matches = not self.has_positive_pattern

        for rule in self.rules:
            if rule.matches(req):
                matches = not rule.negated

        return matches


@dataclass
class LockfileFilter:
    rules: t.Sequence["Rule"]
    has_positive_pattern: bool

    PARAM_TYPE: t.ClassVar[_FilterParamType[t.Any]]  # initialized later
    DEFAULT: t.ClassVar[t.Self]  # initialized later

    @dataclass(kw_only=True)
    class Rule:
        negated: bool
        name: re.Pattern[str]

    @classmethod
    def compile(cls, value: str) -> t.Self:
        rules = _parse_all_rules(value, rule_type=cls.Rule)
        return cls(rules, has_positive_pattern=any(not p.negated for p in rules))

    def matches(self, *, name: str) -> bool:
        # If there's a positive pattern, the default is FALSE,
        # and at least one positive pattern must match.
        # Otherwise, the default is TRUE,
        # and negative patterns may exclude the value.
        matches = not self.has_positive_pattern

        for rule in self.rules:
            if rule.name.fullmatch(name):
                matches = not rule.negated

        return matches

    def filtered_lockfile(self, lockfile: Lockfile) -> Lockfile:
        return {
            "packages": [
                p for p in lockfile["packages"] if self.matches(name=p["name"])
            ]
        }


ConstraintFilter.PARAM_TYPE = _FilterParamType("constraint-filter", ConstraintFilter)
ConstraintFilter.DEFAULT = ConstraintFilter((), has_positive_pattern=False)

LockfileFilter.PARAM_TYPE = _FilterParamType("lockfile-filter", LockfileFilter)
LockfileFilter.DEFAULT = LockfileFilter((), has_positive_pattern=False)


_PATTERN_LITERAL_FRAGMENT = re.compile(r"[a-zA-Z0-9._-]++")


@dataclass
class _Ptr:
    data: str
    i: int = 0

    def eof(self) -> bool:
        return self.i >= len(self.data)

    def consume(self, prefix: t.LiteralString) -> bool:
        if self.data[self.i : self.i + len(prefix)] == prefix:
            self.i += len(prefix)
            return True
        return False

    def peek1(self) -> str:
        return self.data[self.i]

    def skip_ws(self) -> None:
        data, i = self.data, self.i
        n = len(data)
        while i < n and data[i].isspace():
            i += 1
        self.i = i

    def match(self, pattern: re.Pattern[str]) -> re.Match[str] | None:
        if m := pattern.match(self.data, self.i):
            self.i = m.end()
            return m
        return None

    def syntax_error(self, msg: str) -> "_FilterSyntaxError":
        return _FilterSyntaxError(msg, data=self.data, i=self.i)


def _parse_all_rules[R: (LockfileFilter.Rule, ConstraintFilter.Rule)](
    data: str, *, rule_type: type[R]
) -> list[R]:
    p = _Ptr(data)
    rules: list[R] = []
    while True:
        p.skip_ws()
        rules.append(_parse_rule(p, rule_type=rule_type))
        p.skip_ws()
        if p.eof():
            break
        if p.consume(","):
            continue
        # left over content is a syntax error
        raise p.syntax_error("unexpected content after filter rule")

    return rules


def _parse_rule[R: (LockfileFilter.Rule, ConstraintFilter.Rule)](
    p: _Ptr, rule_type: type[R]
) -> R:
    negated: bool = p.consume("!")

    if issubclass(rule_type, LockfileFilter.Rule):
        pattern = _parse_pattern(p)
        if pattern is None:
            raise p.syntax_error("expected filter pattern")

        return rule_type(negated=negated, name=pattern)

    t.assert_type(rule_type, type[ConstraintFilter.Rule])

    p.skip_ws()
    rule = rule_type(negated=negated, name=None, extra=None, group=None)
    if _parse_qualifier_into_rule(p, rule):
        pass
    elif name := _parse_pattern(p):
        rule.name = name
        p.skip_ws()
        _parse_qualifier_into_rule(p, rule)
    else:
        raise p.syntax_error("expected filter pattern or qualifier")
    return rule


def _parse_qualifier_into_rule(p: _Ptr, rule: ConstraintFilter.Rule) -> bool:
    if extra := _parse_qualifier(p, "extra"):
        rule.extra = extra
        return True
    if group := _parse_qualifier(p, "group"):
        rule.group = group
        return True
    return False


def _parse_qualifier(p: _Ptr, name: t.LiteralString) -> re.Pattern[str] | None:
    if not p.consume(f"{name}:"):
        return None
    pattern = _parse_pattern(p)
    if pattern is None:
        raise p.syntax_error("expected pattern")
    return pattern


def _parse_pattern(p: _Ptr) -> re.Pattern[str] | None:
    buf: list[str] = []
    while not p.eof():
        # scan literal package name parts and normalize as per spec at
        # <https://packaging.python.org/en/latest/specifications/name-normalization/>
        if m := p.match(_PATTERN_LITERAL_FRAGMENT):
            buf.append(re.sub(r"[-_.]+", "-", m[0]).lower())
            continue

        # wildcards
        if p.consume("*"):
            buf.append(".*")
            continue
        if p.consume("?"):
            buf.append(".")
            continue

        # explicitly warn about unsupported syntax
        if p.peek1() in "[]":
            raise p.syntax_error("bracket expressions not supported")
        if p.peek1() in "{}":
            raise p.syntax_error("brace expansion not supported")

        break

    if not buf:
        return None

    return re.compile("".join(buf))


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
