import importlib.resources.abc
import pathlib
import tomllib
import typing as t

import pydantic

from ._utils import error_context

type PathLike = pathlib.Path | importlib.resources.abc.Traversable

type Lockfile = dict[str, LockedPackage]


class LockedPackage(t.TypedDict):
    version: str


LOCKFILE_SCHEMA = pydantic.TypeAdapter[Lockfile](Lockfile)


def lockfile_from(path: PathLike) -> Lockfile:
    if path.name.endswith("uv.lock"):
        with error_context(f"while parsing {path}"):
            return _lockfile_from_uv(path)

    raise ValueError(f"unsupported lockfile format in {path}")


class UvLockfilePackage(t.TypedDict):
    name: str
    version: str


class UvLockfile(t.TypedDict):
    version: t.Literal[1]
    package: list[UvLockfilePackage]


_UV_LOCKFILE_SCHEMA = pydantic.TypeAdapter(UvLockfile)


def _lockfile_from_uv(path: PathLike) -> Lockfile:
    uv_lockfile = _UV_LOCKFILE_SCHEMA.validate_python(tomllib.loads(path.read_text()))
    return {
        p["name"]: {
            "version": p["version"],
        }
        for p in uv_lockfile["package"]
    }
