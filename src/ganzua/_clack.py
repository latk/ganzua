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

from ._filters import Filter

type TypeForm = type[object]


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
        if param_type is Filter.PARAM_TYPE:
            args["metavar"] = "FILTER"

        return click.Option(
            name,
            required=False,
            hidden=hidden,
            is_flag=(param_type is click.BOOL),
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

    cmd = cls(name=name, callback=f, help=f.__doc__, params=params, **extra)
    cmd.__doc__ = f.__doc__
    return cmd


def _infer_command_name(name: str) -> str:
    name = name.lower().replace("_", "-")
    return name.removesuffix("-command")


def _infer_param(param: inspect.Parameter) -> click.Parameter:
    if t.get_origin(param.annotation) is t.Annotated:
        ty, *annotations = t.get_args(param.annotation)
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
    if t.get_origin(ty) is types.UnionType:
        match [
            variant
            for variant in t.get_args(ty)
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
    if ty is Filter:
        return Filter.PARAM_TYPE
    if ty is pathlib.Path:
        return click.Path(path_type=pathlib.Path)

    if isinstance(ty, type) and issubclass(ty, enum.Enum):
        return click.Choice(ty, case_sensitive=False)

    if t.get_origin(ty) is t.Literal:
        return click.Choice(t.get_args(ty))

    raise NotImplementedError(f"unsupported type form: {ty}")
