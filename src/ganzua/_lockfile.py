import importlib.resources.abc
import pathlib
import tomllib
import typing as t

import pydantic

from ._utils import error_context

type PathLike = pathlib.Path | importlib.resources.abc.Traversable


class LockedPackage(t.TypedDict):
    version: str


class Lockfile(t.TypedDict):
    packages: dict[str, LockedPackage]


def lockfile_from(path: PathLike) -> Lockfile:
    with error_context(f"while parsing {path}"):
        input_lockfile = _ANY_LOCKFILE_SCHEMA.validate_python(
            tomllib.loads(path.read_text())
        )

        return {
            "packages": {
                p["name"]: {
                    "version": p["version"],
                }
                for p in input_lockfile["package"]
            }
        }


class UvLockfileV1Package(t.TypedDict):
    name: str
    version: str


class UvLockfileV1(t.TypedDict):
    # UV has some lockfile compatibility guarantees:
    # <https://docs.astral.sh/uv/concepts/resolution/#lockfile-versioning>
    # Therefore, we pin this model to only match the v1 schema.
    # Future changes should get their own model.
    version: t.Literal[1]
    package: list[UvLockfileV1Package]


class PoetryLockfileV2Package(t.TypedDict):
    name: str
    version: str


# Must use the functional form of declaring TypedDicts
# because the keys are not valid Python identifiers.
PoetryLockfileV2Metadata = t.TypedDict(
    "PoetryLockfileV2Metadata",
    {
        "lock-version": str,
        "content-hash": str,
    },
)


class PoetryLockfileV2(t.TypedDict):
    # There is no official documentaton for this lockfile format.
    # The `Locker` class comes close:
    # <https://github.com/python-poetry/poetry/blob/1c059eadbb4c2bf29e01a61979b7f50263c9e506/src/poetry/packages/locker.py#L53>
    metadata: PoetryLockfileV2Metadata
    package: list[PoetryLockfileV2Package]


AnyLockfile = t.Annotated[
    UvLockfileV1 | PoetryLockfileV2, pydantic.Field(union_mode="left_to_right")
]

_ANY_LOCKFILE_SCHEMA = pydantic.TypeAdapter[AnyLockfile](AnyLockfile)
