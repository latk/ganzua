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


_TomlAny = _TomlDict | tomlkit.items.Item


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
        return self.container[self.key]

    @t.override
    def replace(self, value: object, /) -> None:
        self.container[self.key] = value


@dataclass(frozen=True)
class RefArrayItem(IRef):
    container: tomlkit.items.Array
    key: int

    @t.override
    def value(self) -> _TomlAny:
        return self.container[self.key]

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
