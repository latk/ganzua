import contextlib
import typing as t


@contextlib.contextmanager
def error_context(ctx: str) -> t.Generator[None, None, None]:
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


def coalesce[T](*values: T | None, default: T) -> T:
    """Return the first non-null value, or the default.

    Examples:
        >>> coalesce(42, None, default=0)
        42
        >>> coalesce(None, 0, default=999)
        0
        >>> coalesce(None, None, default="xyz")
        'xyz'
    """
    for value in values:
        if value is not None:
            return value
    return default
