r"""A kind of DOM for traversing and manipulating TOML documents.

A `Ref` is a view onto part of a `tomlkit.TOMLDocument`.
It knows its location, so the Ref can replace itself with a new value.

Examples for traversing tables:

>>> ref = RefRoot.parse("a = 1\nb = { c = 3 }")
>>> ref["b"].value()
{'c': 3}
>>> ref["a"].value()
1
>>> ref["b"]["c"].value()
3
>>> print(ref["nonexistent"]["keys"].value())
None

We can also traverse interrupted tables, which internally involves a proxy type.

>>> ref = RefRoot.parse('''\
... [table.a]
... content = 1
... [interrupted]
... [table.b]
... content = 2
... ''')
>>> ref["table"].value()
{'a': {'content': 1}, 'b': {'content': 2}}
>>> ref["table"]["b"]["content"].value()
2

Cannot replace root objects:

>>> ref = RefRoot.parse("")
>>> ref.replace({})
Traceback (most recent call last):
NotImplementedError

Cannot replace null objects:

>>> ref["foo"]["bar"].replace(42)
Traceback (most recent call last):
NotImplementedError

"""

import typing as t
from dataclasses import dataclass

import tomlkit.container
import tomlkit.items

type Ref = RefRoot | RefTableItem | RefArrayItem | RefNull

_TomlDict: t.TypeAlias = (
    tomlkit.container.Container
    | tomlkit.container.OutOfOrderTableProxy
    | tomlkit.items.AbstractTable
)


_TomlAny = _TomlDict | tomlkit.items.Item | bool


class IRef(t.Protocol):
    def value(self) -> _TomlAny | None:
        """Get the value of this ref, if any."""
        ...

    def replace(self, value: object, /) -> None:
        """Replace the value of this ref, if possible."""
        ...

    def value_as_str(self) -> str | None:
        value = self.value()
        if not isinstance(value, tomlkit.items.String):
            return None
        return value.value

    def __getitem__(self, key: str) -> "RefTableItem | RefNull":
        container = self.value()
        if isinstance(container, _TomlDict) and key in container:
            return RefTableItem(container, key)
        return RefNull()

    def __contains__(self, key: str) -> bool:
        container = self.value()
        return isinstance(container, _TomlDict) and key in container

    def array_items(self) -> "t.Iterator[RefArrayItem]":
        """If this is an array, iterate over all items."""
        value = self.value()
        if not isinstance(value, tomlkit.items.Array):
            return
        for i in range(len(value)):
            yield RefArrayItem(container=value, key=i)

    def table_entries(self) -> "t.Iterator[RefTableItem]":
        """If this is a table, iterate over all entries."""
        value = self.value()
        if not isinstance(value, _TomlDict):
            return
        for key in value:
            yield RefTableItem(container=value, key=key)


@dataclass(frozen=True)
class RefRoot(IRef):
    root: _TomlDict

    @t.override
    def value(self) -> _TomlDict:
        return self.root

    @t.override
    def replace(self, _value: object, /) -> None:
        raise NotImplementedError

    @classmethod
    def parse(cls, toml: str) -> t.Self:
        return cls(tomlkit.parse(toml))

    def dumps(self) -> str:
        return tomlkit.dumps(self.value())


@dataclass(frozen=True)
class RefTableItem(IRef):
    container: _TomlDict
    key: str

    @t.override
    def value(self) -> _TomlAny:
        value = self.container[self.key]
        assert _is_toml_any(value)  # noqa: S101
        return value

    @t.override
    def replace(self, value: object, /) -> None:
        self.container[self.key] = value


@dataclass(frozen=True)
class RefArrayItem(IRef):
    container: tomlkit.items.Array
    key: int

    @t.override
    def value(self) -> _TomlAny:
        value = self.container[self.key]
        assert _is_toml_any(value)  # noqa: S101
        return value

    @t.override
    def replace(self, value: object, /) -> None:
        self.container[self.key] = value


@dataclass(frozen=True)
class RefNull(IRef):
    @t.override
    def value(self) -> None:
        return None

    @t.override
    def replace(self, _value: object, /) -> None:
        raise NotImplementedError


def _is_toml_any(value: object) -> t.TypeGuard[_TomlAny]:
    """Consistency check that the given value does indeed satisfy `_TomlAny`.

    Compare the list of supported inline values in the spec:
    <https://toml.io/en/v1.1.0#keyvalue-pair>

    >>> _is_toml_any(tomlkit.parse("x = 'abc'")["x"])  # string
    True
    >>> _is_toml_any(tomlkit.parse("x = 123")["x"])  # integer
    True
    >>> _is_toml_any(tomlkit.parse("x = 6.78")["x"])  # float
    True
    >>> _is_toml_any(tomlkit.parse("x = true")["x"])  # boolean
    True
    >>> _is_toml_any(tomlkit.parse("x = false")["x"])  # boolean
    True
    >>> _is_toml_any(tomlkit.parse("x = 2026-07-05T12:19:00+02:00")["x"])  # offset dt
    True
    >>> _is_toml_any(tomlkit.parse("x = 2026-07-05 12:19:00")["x"])  # local dt
    True
    >>> _is_toml_any(tomlkit.parse("x = 2026-07-05")["x"])  # local date
    True
    >>> _is_toml_any(tomlkit.parse("x = 12:19:00")["x"])  # local time
    True
    >>> _is_toml_any(tomlkit.parse("x = [1,2,3]")["x"])  # array
    True
    >>> _is_toml_any(tomlkit.parse("x = {a = 123}")["x"])  # inline table
    True

    Top-level structures:

    >>> _is_toml_any(tomlkit.parse("x = 123"))  # root/table
    True
    >>> _is_toml_any(tomlkit.parse("[section]")["section"])  # table
    True
    >>> _is_toml_any(tomlkit.parse("[[section]]")["section"])  # array of talbes
    True

    Objects that won't appear in a plain TOML document:

    >>> _is_toml_any(None)
    False
    >>> _is_toml_any(123)  # plain numbers
    False
    >>> _is_toml_any([])  # plain collections
    False
    >>> _is_toml_any({})
    False
    """
    match value:
        case (
            tomlkit.container.Container()
            | tomlkit.container.OutOfOrderTableProxy()
            | tomlkit.items.Item()
            | bool()
        ):
            return True
        case _:
            return False
