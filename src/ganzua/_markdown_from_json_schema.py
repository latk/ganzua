import dataclasses
import textwrap
import typing as t
from dataclasses import dataclass

import pydantic
from typing_extensions import TypeIs


class SchemaNotSupportedError(ValueError):
    """Some aspects of this schema weren't understood."""


def md_from_schema(schema: pydantic.JsonValue) -> str:
    """Render the JSON-Schema as a Markdown description."""
    renderer = _Renderer(schema, heading_level=3, anchor_prefix="type.")
    return "\n".join(renderer.md_from_root_recursive())


@dataclass
class _Renderer:
    root: pydantic.JsonValue
    """The top-level Json Schema object, needed for resolving refs."""

    _: dataclasses.KW_ONLY

    heading_level: int

    anchor_prefix: str

    referenced_types: dict[str, bool] = dataclasses.field(default_factory=dict)
    """Collection of referenced types.

    Key: a pointer expression like `#/$defs/Foo`

    Value: False if referenced but not yet emitted. True if emitted.
    """

    def _resolve_ptr(self, ptr: str) -> pydantic.JsonValue:
        if not ptr.startswith("#/"):  # pragma: no cover
            raise SchemaNotSupportedError
        value = self.root
        for key in ptr.removeprefix("#/").split("/"):
            if not isinstance(value, t.Mapping):  # pragma: no cover
                raise SchemaNotSupportedError
            value = value[key]
        return value

    def md_from_root_recursive(self) -> t.Iterable[str]:
        yield from self.md_from_object(self.root, heading=False)

        while True:
            newly_emitted = 0
            for ptr, already_emitted in list(self.referenced_types.items()):
                if already_emitted:
                    continue
                self.referenced_types[ptr] = True
                newly_emitted += 1
                yield from self.md_from_object(self._resolve_ptr(ptr))
            if not newly_emitted:
                break

    def md_from_object(
        self, spec: pydantic.JsonValue, *, heading: bool = True
    ) -> t.Iterable[str]:
        match spec:
            case {"type": "object", "title": str(name), "properties": properties} if (
                properties and (isinstance(properties, t.Mapping))
            ):
                pass
            case _:  # pragma: no cover
                raise SchemaNotSupportedError(spec)

        if heading:
            atx_header = "#" * self.heading_level
            yield f"{atx_header} type `{name}` {{#{self.anchor_prefix}{name}}}"
            yield ""

        match spec:
            case {"description": str(description)}:
                yield description
                yield ""

        match spec:
            case {"required": [*required]}:
                if not _all_are_strings(required):  # pragma: no cover
                    raise SchemaNotSupportedError(spec)
            case _:  # pragma: no cover
                raise SchemaNotSupportedError(spec)

        yield "**Properties:**"
        yield ""
        for prop, prop_spec in properties.items():
            prop_md = self.md_from_property(
                prop, prop_spec, required=(prop in required)
            )
            yield f"* {textwrap.indent(prop_md, '  ').strip()}"
        yield ""

    def md_from_property(
        self, name: str, spec: pydantic.JsonValue, *, required: bool
    ) -> str:
        required_marker = "" if required else "?"
        type_expression = self.md_from_type_reference(spec)
        md = f"**`{name}`**{required_marker}: {type_expression}"

        match spec:
            case {"description": description}:
                md = f"{md}\\\n{description}"

        return md

    def md_from_type_reference(  # noqa: C901 # complexity
        self, spec: pydantic.JsonValue
    ) -> str:
        match spec:
            case {"anyOf": [*variants]}:
                return " | ".join(self.md_from_type_reference(v) for v in variants)
            case {"type": "string", "enum": [*enum]} if _all_are_strings(enum):
                return " | ".join(f"`{e}`" for e in enum)
            case {"type": "string"}:
                return "string"
            case {"type": "boolean"}:
                return "bool"
            case {"type": "integer"}:
                return "int"
            case {"type": "null"}:
                return "null"
            case {"type": "object", "properties": _}:  # pragma: no cover
                raise SchemaNotSupportedError(spec)
            case {"type": "object", "additionalProperties": value_type}:
                return f"map(string → {self.md_from_type_reference(value_type)})"
            case {"type": "array", "items": item_type}:
                return f"array({self.md_from_type_reference(item_type)})"
            case {"$ref": str(ptr)}:
                self.referenced_types.setdefault(ptr, False)
                name = self._resolve_ptr(f"{ptr}/title")
                if not isinstance(name, str):  # pragma: no  cover
                    raise SchemaNotSupportedError(spec)
                return f"[{name}](#{self.anchor_prefix}{name})"
            case _:  # pragma: no cover
                raise SchemaNotSupportedError(spec)


def _all_are_strings(value: t.Sequence[pydantic.JsonValue]) -> TypeIs[t.Sequence[str]]:
    return all(isinstance(x, str) for x in value)
