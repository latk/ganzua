import pathlib
import typing as t

import pytest

CLICK_ERROR = 2
"""The exit code used by Click by default."""


type Decorator[F] = t.Callable[[F], F]


def parametrized[T, F: t.Callable[..., t.Any]](
    argname: str, cases: dict[str, T]
) -> Decorator[F]:
    """More convenient test parametrization, using a dict to provide names for each case.

    ```python
    @parametrized("arg", {"foo": 1, "bar": 2})
    def test_something(arg: int): ...
    ```
    """
    return pytest.mark.parametrize(
        argname, [pytest.param(value, id=key) for key, value in cases.items()]
    )


@t.overload
def write_file(dest: str | pathlib.Path, *, source: pathlib.Path) -> pathlib.Path: ...


@t.overload
def write_file(dest: str | pathlib.Path, *, data: str) -> pathlib.Path: ...


def write_file(
    dest: str | pathlib.Path,
    *,
    source: pathlib.Path | None = None,
    data: str | None = None,
) -> pathlib.Path:
    """Copy the `source` contents into the `dest` file.

    Returns the `dest` path.
    """
    dest = pathlib.Path(dest)
    match (source, data):
        case pathlib.Path(), None:
            dest.write_bytes(source.read_bytes())
        case None, str():
            dest.write_text(data)
        case _:  # pragma: no cover
            raise AssertionError(f"unreachable: {source=} {data=}")
    return dest
