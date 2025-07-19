import importlib.resources
import pathlib

_RESOURCES = importlib.resources.files()

OLD_UV_LOCKFILE = _RESOURCES / "old-uv-project/uv.lock"
NEW_UV_LOCKFILE = _RESOURCES / "new-uv-project/uv.lock"
EMPTY = pathlib.Path("/dev/null")
