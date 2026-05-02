import contextlib
import dataclasses
import json
import textwrap
import typing as t
from dataclasses import dataclass

import pydantic
from typing_extensions import TypeIs


class SchemaNotSupportedError(ValueError):
    """Some aspects of this schema weren't understood."""


def md_from_schema(schema: pydantic.JsonValue) -> str:
    """Render the JSON-Schema as a Markdown description."""
    resolver = _Resolver(schema)
    renderer = _Renderer(heading_level=3, anchor_prefix="type.")
    return "\n".join(renderer.md_from_root_recursive(resolver.resolve(schema))).strip()


type _SchemaType = _SchemaObject | _SchemaUnion | _SchemaArray | _SchemaPrimitive


@dataclass(eq=False)
class _SchemaObject:
    name: str | None
    description: str | None
    properties: "list[_SchemaProperty]"


@dataclass(eq=False)
class _SchemaProperty:
    name: str
    type: _SchemaType
    required: bool
    description: str | None


@dataclass(eq=False)
class _SchemaUnion:
    name: str | None
    description: str | None
    variants: list[_SchemaType]


@dataclass(eq=False)
class _SchemaArray:
    items: _SchemaType


@dataclass(eq=False)
class _SchemaPrimitive:
    name: str


@dataclass
class _Resolver:
    root: pydantic.JsonValue
    """The top-level JSON Schema object, needed for resolving refs."""

    ref_cache: dict[str, _SchemaType] = dataclasses.field(default_factory=dict)

    def resolve(  # noqa: C901 # complexity
        self, spec: pydantic.JsonValue
    ) -> _SchemaType:
        match spec:
            case {"$ref": str(ptr)}:
                return self._resolve_ptr_cached(ptr)
            case {"type": "object"}:
                return self._resolve_object(spec)
            case {"anyOf": [*variants]} if variants:
                return _SchemaUnion(
                    name=_get_str(spec, "title"),
                    description=_get_str(spec, "description"),
                    variants=[self.resolve(v) for v in variants],
                )
            case {"type": "string", "enum": [*enum]} if _all_are_strings(enum):
                return _SchemaPrimitive(" | ".join(f"`{e}`" for e in enum))
            case {"const": value}:
                value = json.dumps(value)
                return _SchemaPrimitive(f"`{value}`")
            case {"type": "string"}:
                return _SchemaPrimitive("string")
            case {"type": "boolean"}:
                return _SchemaPrimitive("bool")
            case {"type": "integer"}:
                return _SchemaPrimitive("int")
            case {"type": "null"}:
                return _SchemaPrimitive("null")
            case {"type": "array", "items": item_type}:
                return _SchemaArray(self.resolve(item_type))
            case _:
                raise SchemaNotSupportedError(spec)

    def _get_ptr(self, ptr: str) -> pydantic.JsonValue:
        if not ptr.startswith("#/"):
            raise SchemaNotSupportedError
        spec = self.root
        for key in ptr.removeprefix("#/").split("/"):
            if not isinstance(spec, t.Mapping):
                raise SchemaNotSupportedError
            spec = spec[key]
        return spec

    def _resolve_ptr_cached(self, ptr: str) -> _SchemaType:
        if ty := self.ref_cache.get(ptr):
            return ty
        ty = self.ref_cache[ptr] = self.resolve(self._get_ptr(ptr))
        return ty

    def _resolve_object(self, spec: pydantic.JsonValue) -> _SchemaObject:
        name = _get_str(spec, "title")
        description = _get_str(spec, "description")

        match spec:
            case {"properties": props} if props and isinstance(props, t.Mapping):
                pass
            case _:
                raise SchemaNotSupportedError(spec)

        match spec:
            case {"required": [*required]}:
                if not _all_are_strings(required):
                    raise SchemaNotSupportedError(spec)
            case _:
                required = list[str]()

        resolved_properties = [
            self._resolve_property(name, prop_spec, required=(name in required))
            for name, prop_spec in props.items()
        ]
        return _SchemaObject(
            name, description=description, properties=resolved_properties
        )

    def _resolve_property(
        self, name: str, spec: pydantic.JsonValue, *, required: bool
    ) -> _SchemaProperty:
        description = _get_str(spec, "description")
        return _SchemaProperty(
            name, self.resolve(spec), required=required, description=description
        )


@dataclass(kw_only=True)
class _Renderer:
    heading_level: int

    anchor_prefix: str

    referenced_types: list[_SchemaObject] = dataclasses.field(default_factory=list)

    @contextlib.contextmanager
    def _capture_new_referenced_types(
        self, stack: list[_SchemaObject]
    ) -> t.Iterator[None]:
        try:
            yield
        finally:
            stack.extend(reversed(self.referenced_types))
            self.referenced_types.clear()

    def md_from_root_recursive(self, spec: _SchemaType) -> t.Iterable[str]:
        emitted = set[_SchemaObject]()
        stack = list[_SchemaObject]()
        with self._capture_new_referenced_types(stack):
            yield from self.md_from_object(spec, heading=False)

        while stack:
            ref = stack.pop()
            if ref in emitted:
                continue
            emitted.add(ref)
            with self._capture_new_referenced_types(stack):
                yield from self.md_from_object(ref)

    def md_from_object(
        self, spec: _SchemaType, *, heading: bool = True
    ) -> t.Iterable[str]:
        if heading:
            match spec:
                case _SchemaObject(name=str(name)):
                    atx_header = "#" * self.heading_level
                    yield f"{atx_header} type `{name}` {{#{self.anchor_prefix}{name}}}"
                    yield ""
                case _:
                    raise SchemaNotSupportedError(spec)

        match spec:
            case _SchemaObject() | _SchemaUnion() if spec.description:
                yield spec.description
                yield ""

        match spec:
            case _SchemaObject():
                yield from self.md_from_properties(spec.properties)

        match spec:
            case _SchemaUnion():
                yield from self.md_from_variants(spec.variants)

    def md_from_variants(self, variants: t.Sequence[_SchemaType]) -> t.Iterable[str]:
        yield "**Variants:**"
        yield ""
        for variant in variants:
            yield f"* {self.md_from_type_reference(variant)}"
        yield ""

    def md_from_properties(
        self, properties: t.Sequence[_SchemaProperty]
    ) -> t.Iterable[str]:
        yield "**Properties:**"
        yield ""
        for prop in properties:
            prop_md = self.md_from_property(prop)
            yield f"* {textwrap.indent(prop_md, '  ').strip()}"
        yield ""

    def md_from_property(self, prop: _SchemaProperty) -> str:
        # inline small objects into the property description
        small_object = 2
        inline_properties = None
        match prop.type:
            case _SchemaObject() if (
                not prop.type.description and len(prop.type.properties) <= small_object
            ):
                inline_properties = prop.type.properties
                type_expression = "object"
            case _:
                type_expression = self.md_from_type_reference(prop.type)
        required_marker = "" if prop.required else "?"
        md = f"**`{prop.name}`**{required_marker}: {type_expression}"

        if prop.description:
            md = f"{md}\\\n{prop.description}"

        if inline_properties:
            md += "\n\n" + "\n".join(self.md_from_properties(inline_properties))

        return md

    def md_from_type_reference(self, spec: _SchemaType) -> str:
        match spec:
            case _SchemaObject() if spec.name:
                self.referenced_types.append(spec)
                return f"[{spec.name}](#{self.anchor_prefix}{spec.name})"
            case _SchemaUnion():
                return " | ".join(self.md_from_type_reference(v) for v in spec.variants)
            case _SchemaArray():
                item_md = self.md_from_type_reference(spec.items)
                return f"array({item_md})"
            case _SchemaPrimitive():
                return spec.name
            case _:
                raise SchemaNotSupportedError(spec)


def _all_are_strings(value: t.Sequence[pydantic.JsonValue]) -> TypeIs[t.Sequence[str]]:
    return all(isinstance(x, str) for x in value)


def _get_str(spec: pydantic.JsonValue, name: str) -> str | None:
    if (
        isinstance(spec, t.Mapping)
        and (value := spec.get(name))
        and isinstance(value, str)
    ):
        return value.strip()
    return None
