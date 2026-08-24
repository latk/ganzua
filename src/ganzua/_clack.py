"""Command Line Application Control Kit (CLACK) is a Click wrapper.

Click is very dynamic, and requires repetitive definitions in a code base with static typing.
This Clack wrapper is a very thin type-driven wrapper over Click functionality.

Click command:

```python
@click.command()
@click.option("--foo", type=int, help="foo bar")
def some_command(foo: int) -> None:
    print(foo)
```

Clack command:

```python
@clack.command()
def some_command(
    foo: t.Annotated[int, clack.Option(help="foo bar")],
) -> None:
    print(foo)
```
"""

import dataclasses
import enum
import inspect
import pathlib
import types
import typing as t
from dataclasses import dataclass

import click

from ._filters import ConstraintFilter, LockfileFilter

type TypeForm = type[object] | t.TypeAliasType | None


class ExtraCommandArgs(t.TypedDict, total=False):
    add_help_option: bool


class ClickParamArgs(t.TypedDict, total=False):
    type: t.Required[click.ParamType]
    help: str
    default: object
    metavar: str


UNSET = inspect.Parameter.empty


def command(
    name: str | None = None,
    *,
    cls: type[click.Command] = click.Command,
    **extra: t.Unpack[ExtraCommandArgs],
) -> t.Callable[[t.Callable[..., None]], click.Command]:
    def decorator(f: t.Callable[..., None]) -> click.Command:
        return _infer_command(f, name=name, cls=cls, **extra)

    return decorator


@dataclass
class Option:
    """Annotation for named options."""

    name: str | None = None
    _: dataclasses.KW_ONLY
    help: str | None
    type: click.ParamType | None = None
    deprecated: str | None = None
    metavar: str | None = None

    def to_click(self, field_name: str, ty: TypeForm, default: object) -> click.Option:
        name = [
            self.name or f"--{field_name.replace('_', '-')}",
            field_name,
        ]

        param_type = self.type or _infer_param_type(ty)
        args = ClickParamArgs(type=param_type)
        if not (hidden := self.help is None):
            args["help"] = self.help
        if default is UNSET:  # pragma: no cover
            raise TypeError("required options not implemented")
        args["default"] = default

        return click.Option(
            name,
            required=False,
            hidden=hidden,
            is_flag=(param_type is click.BOOL),
            deprecated=self.deprecated or False,
            metavar=self.metavar,
            **args,
        )


@dataclass
class Argument:
    """Annotation for positional arguments."""

    _: dataclasses.KW_ONLY
    type: click.ParamType | None = None

    def to_click(
        self, field_name: str, ty: TypeForm, default: object
    ) -> click.Argument:
        args = ClickParamArgs(type=self.type or _infer_param_type(ty))
        if not (required := default is UNSET):
            args["default"] = default

        return click.Argument([field_name], **args, required=required)


def _infer_command(
    f: t.Callable[..., None],
    name: str | None = None,
    cls: type[click.Command] = click.Command,
    **extra: t.Unpack[ExtraCommandArgs],
) -> click.Command:
    # Compare: <https://github.com/pallets/click/blob/8bd8b4a074c55c03b6eb5666edc44a9c43df38a2/src/click/decorators.py#L168>

    params = [_infer_param(p) for p in inspect.signature(f).parameters.values()]

    if name is None:
        name = _infer_command_name(f.__name__)

    doc = inspect.getdoc(f) or ""
    prolog, _, epilog = doc.partition("\n<!-- options -->\n")
    cmd = cls(
        name=name,
        callback=f,
        help=prolog.strip() or None,
        params=params,
        epilog=epilog.strip() or None,
        **extra,
    )
    cmd.__doc__ = f.__doc__
    return cmd


def _infer_command_name(name: str) -> str:
    name = name.lower().replace("_", "-")
    return name.removesuffix("-command")


def _infer_param(param: inspect.Parameter) -> click.Parameter:
    ty, annotations = _expand_annotations(param.annotation)
    for ann in annotations:
        match ann:
            case click.Parameter():
                return ann
            case Argument() | Option():
                return ann.to_click(param.name, ty, param.default)
            case _:  # pragma: no cover # ignore any other annotations
                pass

    raise NotImplementedError(f"{param=}")


def _infer_param_type(ty: TypeForm) -> click.ParamType:
    """Convert a Python type to a Click param.

    >>> _infer_param_type(t.Optional[str])
    STRING
    """
    match [
        variant
        for variant in _expand_union_type(ty)
        if variant is not None and variant is not types.NoneType
    ]:
        case [single_variant]:
            ty = single_variant
        case _:
            raise NotImplementedError(
                f"only `X | None` unions are supported, but got: {ty}"
            )

    if ty is str:
        return click.STRING
    if ty is bool:
        return click.BOOL
    if ty in (ConstraintFilter, LockfileFilter):
        return ty.PARAM_TYPE
    if ty is pathlib.Path:
        return click.Path(path_type=pathlib.Path)

    if isinstance(ty, type) and issubclass(ty, enum.Enum):
        return click.Choice(ty, case_sensitive=False)

    if t.get_origin(ty) is t.Literal:
        return click.Choice(t.get_args(ty))

    raise NotImplementedError(f"unsupported type form: {ty!r}")


def _expand_annotations(ty: TypeForm) -> tuple[TypeForm, list[object]]:
    annotations: list[object] = []
    while t.get_origin(ty) is t.Annotated:
        ty, *more_annotations = t.get_args(ty)
        annotations[:0] = more_annotations
    return ty, annotations


def _expand_union_type(ty: TypeForm) -> t.Iterable[TypeForm]:
    if t.get_origin(ty) in (types.UnionType, t.Union):
        for variant in t.get_args(ty):
            yield from _expand_union_type(variant)
        return

    yield ty
    return
