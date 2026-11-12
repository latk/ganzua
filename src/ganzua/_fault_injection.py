import contextlib
import contextvars
import typing as t

import pydantic


@pydantic.with_config(use_attribute_docstrings=True)
class State(t.TypedDict, total=False):
    """Faults that may be injected during doctests."""

    pypi_metadata_invalid_response: t.Literal[True]
    """Inject a JSON body that will cause validation errors while parsing a PyPI metadata response."""


_ACTIVE_FAULTS = contextvars.ContextVar[State]("_ACTIVE_FAULTS")


@contextlib.contextmanager
def scope() -> t.Generator[State, None, None]:
    state = State()
    token = _ACTIVE_FAULTS.set(state)
    try:
        yield state
    finally:
        _ACTIVE_FAULTS.reset(token)


def current() -> State:
    return _ACTIVE_FAULTS.get(State())
