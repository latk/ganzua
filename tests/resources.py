import importlib.resources
import pathlib
import typing as t
from importlib.resources.abc import Traversable

_RESOURCES = importlib.resources.files()

OLD_UV_LOCKFILE = _RESOURCES / "old-uv-project/uv.lock"
NEW_UV_LOCKFILE = _RESOURCES / "new-uv-project/uv.lock"
OLD_UV_PYPROJECT = _RESOURCES / "old-uv-project/pyproject.toml"
NEW_UV_PYPROJECT = _RESOURCES / "new-uv-project/pyproject.toml"
OLD_POETRY_LOCKFILE = _RESOURCES / "old-poetry-project/poetry.lock"
NEW_POETRY_LOCKFILE = _RESOURCES / "new-poetry-project/poetry.lock"
EMPTY = pathlib.Path("/dev/null")


def schema(name: t.Literal["inspect", "diff"]) -> Traversable:
    """Provide a path to the file that contains the current known schema."""
    # TODO I don't like this. The schema should somehow be part of the docs,
    # not just a test resource.
    # Maybe there should be a single schema file for the entire application.
    return _RESOURCES / f"schema.{name}.json"
