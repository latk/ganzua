import contextlib
import typing as t


@contextlib.contextmanager
def error_context(ctx: str) -> t.Iterator[None]:
    """Attach a note with that context to any errors raised within this scope.

    Example: adds a note

    >>> with error_context("while doing something"):
    ...     raise RuntimeError("oops")
    Traceback (most recent call last):
    RuntimeError: oops
    while doing something
    """
    try:
        yield
    except Exception as e:
        e.add_note(ctx)
        raise
