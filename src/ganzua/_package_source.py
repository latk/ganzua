import typing as t


class SourceRegistry(t.TypedDict):
    """The package is sourced from a third party registry."""

    registry: str
    """URL or path to the registry."""


class SourceDirect(t.TypedDict):
    """The package is sourced from a specific URL or path, e.g. a Git repo or workspace path."""

    direct: str
    """URL or path to the package (directory or archive)."""
    subdirectory: t.NotRequired[str]
    """Only allowed if the source points to an archive file."""


Source = t.Literal["pypi", "default", "other"] | SourceRegistry | SourceDirect
"""Known package sources.

* `pypi`: The package is sourced from the official PyPI.
* `default`: The package is not linked to a specific source.
* `other`: The package source cannot be represented by Ganzua.
"""
