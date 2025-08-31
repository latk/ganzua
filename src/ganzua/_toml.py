r"""A kind of DOM for traversing and manipulating TOML documents.

A `TomlRef` is a view onto part of a `tomlkit.TOMLDocument`.
It knows its location, so the Ref can replace itself with a new value.

Examples for traversing tables:

>>> ref = TomlRefRoot(tomlkit.parse("a = 1\nb = { c = 3 }"))
>>> ref["b"].value()
{'c': 3}
>>> ref["a"].value()
1
>>> ref["b"]["c"].value()
3
>>> print(ref["nonexistent"]["keys"].value())
None

We can also traverse interrupted tables, which internally involves a proxy type.

>>> ref = TomlRefRoot(tomlkit.parse('''\
... [table.a]
... content = 1
... [interrupted]
... [table.b]
... content = 2
... '''))
>>> ref["table"].value()
{'a': {'content': 1}, 'b': {'content': 2}}
>>> ref["table"]["b"]["content"].value()
2

Cannot replace root objects:

>>> ref = TomlRefRoot(tomlkit.parse(""))
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

type TomlRef = TomlRefRoot | TomlRefTableItem | TomlRefArrayItem | TomlRefNull

TomlDict: t.TypeAlias = (
    tomlkit.container.Container
    | tomlkit.container.OutOfOrderTableProxy
    | tomlkit.items.AbstractTable
)


TomlAny = TomlDict | tomlkit.items.Item


class ITomlRef(t.Protocol):
    def value(self) -> TomlAny | None:
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

    def __getitem__(self, key: str) -> "TomlRefTableItem | TomlRefNull":
        container = self.value()
        if isinstance(container, TomlDict) and key in container:
            return TomlRefTableItem(container, key)
        return TomlRefNull()

    def __contains__(self, key: str) -> bool:
        container = self.value()
        return isinstance(container, TomlDict) and key in container

    def array_items(self) -> "t.Iterator[TomlRefArrayItem]":
        """If this is an array, iterate over all items."""
        value = self.value()
        if not isinstance(value, tomlkit.items.Array):
            return
        for i in range(len(value)):
            yield TomlRefArrayItem(container=value, key=i)

    def table_entries(self) -> "t.Iterator[TomlRefTableItem]":
        """If this is a table, iterate over all entries."""
        value = self.value()
        if not isinstance(value, TomlDict):
            return
        for key in value:
            yield TomlRefTableItem(container=value, key=key)


@dataclass(frozen=True)
class TomlRefRoot(ITomlRef):
    root: TomlDict

    @t.override
    def value(self) -> TomlDict:
        return self.root

    @t.override
    def replace(self, _value: object, /) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class TomlRefTableItem(ITomlRef):
    container: TomlDict
    key: str

    @t.override
    def value(self) -> TomlAny:
        return self.container[self.key]

    @t.override
    def replace(self, value: object, /) -> None:
        self.container[self.key] = value


@dataclass(frozen=True)
class TomlRefArrayItem(ITomlRef):
    container: tomlkit.items.Array
    key: int

    @t.override
    def value(self) -> TomlAny:
        return self.container[self.key]

    @t.override
    def replace(self, value: object, /) -> None:
        self.container[self.key] = value


@dataclass(frozen=True)
class TomlRefNull(ITomlRef):
    @t.override
    def value(self) -> None:
        return None

    @t.override
    def replace(self, _value: object, /) -> None:
        raise NotImplementedError
