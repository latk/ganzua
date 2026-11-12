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

import contextlib
import dataclasses
import enum
import inspect
import itertools
import pathlib
import types
import typing as t
from dataclasses import dataclass

import click
import yarl

from ._filters import ConstraintFilter, LockfileFilter

type _TypeForm = type[object] | t.TypeAliasType | None
type _VoidFunction = t.Callable[..., None]


class ExtraCommandArgs(t.TypedDict, total=False):
    add_help_option: bool


class ClickParamArgs(t.TypedDict, total=False):
    type: t.Required[click.ParamType]
    help: str
    default: object


UNSET = inspect.Parameter.empty


def command(
    name: str | None = None,
    *,
    cls: type[click.Command] = click.Command,
    **extra: t.Unpack[ExtraCommandArgs],
) -> t.Callable[[_VoidFunction], click.Command]:
    def decorator(f: _VoidFunction) -> click.Command:
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

    def __post_init__(self) -> None:
        if self.help:
            self.help = self.help.rstrip()

    def to_click(self, field_name: str, ty: _TypeForm, default: object) -> click.Option:
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
        self, field_name: str, ty: _TypeForm, default: object
    ) -> click.Argument:
        args = ClickParamArgs(type=self.type or _infer_param_type(ty))
        if not (required := default is UNSET):
            args["default"] = default

        return click.Argument([field_name], **args, required=required)


class UsageError(Exception):
    pass


def _infer_command(
    f: _VoidFunction,
    name: str | None = None,
    cls: type[click.Command] = click.Command,
    **extra: t.Unpack[ExtraCommandArgs],
) -> click.Command:
    # Compare: <https://github.com/pallets/click/blob/8bd8b4a074c55c03b6eb5666edc44a9c43df38a2/src/click/decorators.py#L168>

    params = list[click.Parameter]()
    reducers = list[_Reducer]()
    for p in inspect.signature(f).parameters.values():
        for param_or_reducer in _infer_param(p):
            if isinstance(param_or_reducer, click.Parameter):
                params.append(param_or_reducer)
            else:
                reducers.append(param_or_reducer)

    def flattened_function(**kwargs: object) -> None:
        ctx = click.get_current_context()
        try:
            for reducer in reducers:
                reducer.apply(kwargs)
            return f(**kwargs)
        except UsageError as err:
            msg = str(err)
            match getattr(err, "__notes__", None):
                case [*notes]:
                    for note in notes:
                        msg += f"\nNote: {note}"
            raise click.UsageError(msg, ctx) from None

    if name is None:
        name = _infer_command_name(f.__name__)

    doc = inspect.getdoc(f) or ""
    prolog, _, epilog = doc.partition("\n<!-- options -->\n")
    cmd = cls(
        name=name,
        callback=flattened_function,
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


@dataclasses.dataclass
class _Reducer:
    dest: str
    inputs: t.Sequence[str]
    op: t.Callable[..., object]

    def apply(self, kwargs: dict[str, object]) -> None:
        # Pick out all known parameter names.
        # Nonexistent input kwargs may be OK due to defaults (thus: suppress KeyError).
        # Don't validate that ourselves, instead the op() may raise a TypeError.
        self = self
        inner_kwargs = {}
        for name in self.inputs:
            with contextlib.suppress(KeyError):
                inner_kwargs[name] = kwargs.pop(name)
            kwargs[self.dest] = self.op(**inner_kwargs)


def _infer_param(
    param: inspect.Parameter | dataclasses.Field,
) -> t.Iterable[click.Parameter | _Reducer]:
    match param:
        case inspect.Parameter():
            ty, annotations = _expand_annotations(param.annotation)
        case dataclasses.Field() if not isinstance(param.type, str):
            ty, annotations = _expand_annotations(param.type)
        case _:  # pragma: no cover
            raise NotImplementedError(f"{param=}")

    for ann in annotations:
        match ann:
            case click.Parameter():
                return [ann]
            case Argument() | Option():
                return [ann.to_click(param.name, ty, param.default)]
            case _:  # pragma: no cover # ignore any other annotations
                pass

    # Flatten dataclasses into the function signature.
    if isinstance(ty, type) and dataclasses.is_dataclass(ty):
        fields = dataclasses.fields(ty)
        reducer = _Reducer(dest=param.name, inputs=[f.name for f in fields], op=ty)
        return itertools.chain(*(_infer_param(field) for field in fields), [reducer])

    raise NotImplementedError(f"{param=}")


def _infer_param_type(ty: _TypeForm) -> click.ParamType:
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
    if ty is yarl.URL:
        return _YarlParamType()

    if isinstance(ty, type) and issubclass(ty, enum.Enum):
        return click.Choice(ty, case_sensitive=False)

    if t.get_origin(ty) is t.Literal:
        return click.Choice(t.get_args(ty))

    raise NotImplementedError(f"unsupported type form: {ty!r}")


def _expand_annotations(ty: _TypeForm) -> tuple[_TypeForm, list[object]]:
    annotations: list[object] = []
    while t.get_origin(ty) is t.Annotated:
        ty, *more_annotations = t.get_args(ty)
        annotations[:0] = more_annotations
    return ty, annotations


def _expand_union_type(ty: _TypeForm) -> t.Iterable[_TypeForm]:
    if t.get_origin(ty) in (types.UnionType, t.Union):
        for variant in t.get_args(ty):
            yield from _expand_union_type(variant)
        return

    yield ty
    return


class _YarlParamType(click.ParamType[yarl.URL]):
    """Adapt the YARL URL parser for Click.

    Basic examples:

    >>> p = _YarlParamType()
    >>> p.convert("https://example.com", None, None)
    URL('https://example.com')
    >>> p.convert(yarl.URL("https://example.com"), None, None)
    URL('https://example.com')

    Examples of errors:

    >>> p.convert(None, None, None)
    Traceback (most recent call last):
    click.exceptions.BadParameter: url must be a string: None

    >>> p.convert("ftp://example.com", None, None)
    Traceback (most recent call last):
    click.exceptions.BadParameter: url must use `http:` or `https:` scheme: 'ftp://example.com'

    >>> p.convert("https:./relative", None, None)
    Traceback (most recent call last):
    click.exceptions.BadParameter: url must be absolute: 'https:./relative'
    """

    name = "url"

    @t.override
    def convert(
        self, value: object, param: click.Parameter | None, ctx: click.Context | None
    ) -> yarl.URL:
        if isinstance(value, yarl.URL):
            url = value
        elif isinstance(value, str):
            url = yarl.URL(value)
        else:
            self.fail(f"url must be a string: {value!r}", param, ctx)

        if url.scheme not in ("http", "https"):
            self.fail(f"url must use `http:` or `https:` scheme: {value!r}", param, ctx)
        if not url.absolute:
            self.fail(f"url must be absolute: {value!r}", param, ctx)

        return url
