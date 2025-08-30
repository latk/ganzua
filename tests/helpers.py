import typing as t

import pytest

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
