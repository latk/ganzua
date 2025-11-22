import typing as t

import pydantic
from pydantic.dataclasses import dataclass  # for docstring support


def _is_none(value: object) -> bool:
    return value is None


@dataclass
@pydantic.with_config(use_attribute_docstrings=True)
class SourceRegistry:
    """The package is sourced from a third party registry."""

    registry: str
    """URL or path to the registry."""


@dataclass
@pydantic.with_config(use_attribute_docstrings=True)
class SourceDirect:
    """The package is sourced from a specific URL or path, e.g. a Git repo or workspace path."""

    direct: str
    """URL or path to the package (directory or archive)."""
    subdirectory: t.Annotated[str | None, pydantic.Field(exclude_if=_is_none)] = None
    """Only allowed if the source points to an archive file."""


Source = t.Literal["pypi", "default", "other"] | SourceRegistry | SourceDirect
"""Known package sources.

* `pypi`: The package is sourced from the official PyPI.
* `default`: The package is not linked to a specific source.
* `other`: The package source cannot be represented by Ganzua.
"""
