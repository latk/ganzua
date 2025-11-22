import importlib.resources
import pathlib

_RESOURCES = importlib.resources.files()

OLD_UV_LOCKFILE = _RESOURCES / "old-uv-project/uv.lock"
NEW_UV_LOCKFILE = _RESOURCES / "new-uv-project/uv.lock"
MINOR_UV_LOCKFILE = _RESOURCES / "minor-uv-project/uv.lock"
OLD_UV_PYPROJECT = _RESOURCES / "old-uv-project/pyproject.toml"
NEW_UV_PYPROJECT = _RESOURCES / "new-uv-project/pyproject.toml"
OLD_POETRY_LOCKFILE = _RESOURCES / "old-poetry-project/poetry.lock"
NEW_POETRY_LOCKFILE = _RESOURCES / "new-poetry-project/poetry.lock"
NEW_POETRY_PYPROJECT = _RESOURCES / "new-poetry-project/pyproject.toml"
SOURCES_POETRY_LOCKFILE = _RESOURCES / "sources-poetry/poetry.lock"
SOURCES_UV_LOCKFILE = _RESOURCES / "sources-uv/uv.lock"

README = _RESOURCES / "../README.md"
EMPTY = pathlib.Path("/dev/null")
