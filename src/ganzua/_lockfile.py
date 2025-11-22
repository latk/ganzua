import importlib.resources.abc
import pathlib
import tomllib
import typing as t
from dataclasses import dataclass

import pydantic
import yarl

from ._package_source import Source, SourceDirect, SourceRegistry
from ._utils import error_context

type PathLike = pathlib.Path | importlib.resources.abc.Traversable

UNDEFINED_VERSION = "0+undefined"
"""Use this version when a locked package has no version.

The uv frontend doesn't guarantee that each package has a version.
This can happen in particular for editable installs with setuptools projects
that use a dynamic version, see <https://github.com/latk/ganzua/issues/4>.
"""


class LockedPackage(t.TypedDict):
    version: str
    source: Source


class Lockfile(t.TypedDict):
    packages: dict[str, LockedPackage]


def lockfile_from(path: PathLike) -> Lockfile:
    with error_context(f"while parsing {path}"):
        input_lockfile = _ANY_LOCKFILE_SCHEMA.validate_python(
            tomllib.loads(path.read_text())
        )

        match input_lockfile:
            case UvLockfileV1(package=packages):
                return Lockfile(
                    packages={
                        p["name"]: LockedPackage(
                            version=p.get("version", UNDEFINED_VERSION),
                            source=_map_uv_source(p["source"]),
                        )
                        for p in packages
                    }
                )
            case PoetryLockfileV2(package=packages):
                return Lockfile(
                    packages={
                        p["name"]: LockedPackage(
                            version=p["version"],
                            source=_map_poetry_source(p.get("source")),
                        )
                        for p in packages
                    }
                )
            case other:  # pragma: no cover
                t.assert_never(other)


class UvLockfileV1Source(t.TypedDict, total=False):
    # Only ONE field may be set (or url+subdirectory)

    # The lockfile sources do not match the [tool.uv.sources] syntax
    # https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-sources
    # Instead, the possible sources are defined here:
    # https://github.com/astral-sh/uv/blob/141369ce73b7b0b4e005b0f45107d13c828a99e0/crates/uv-resolver/src/lock/mod.rs#L3736

    registry: str
    """URL or path pointing to an index."""

    git: str

    # direct
    url: str
    subdirectory: t.NotRequired[str]

    # path-style dependencies
    path: str
    directory: str
    editable: str
    virtual: str


class UvLockfileV1Package(t.TypedDict):
    name: str
    version: t.NotRequired[str]
    source: UvLockfileV1Source


@dataclass
class UvLockfileV1:
    # UV has some lockfile compatibility guarantees:
    # <https://docs.astral.sh/uv/concepts/resolution/#lockfile-versioning>
    # Therefore, we pin this model to only match the v1 schema.
    # Future changes should get their own model.
    version: t.Literal[1]
    package: list[UvLockfileV1Package]


class PoetryLockfileV2Source(t.TypedDict, total=False):
    # Source information as defined by Poetry.
    # https://github.com/python-poetry/poetry/blob/17db1da55ab6aac011e33434e8d80a76780ff056/src/poetry/packages/locker.py#L358-L373
    type: str
    """One of `directory`, `file`, `url`, `git`, `hg`, `legacy`, `pypi`.
    The `pypi` name is not case sensitive."""
    url: str
    reference: str
    resolved_reference: str
    subdirectory: str


class PoetryLockfileV2Package(t.TypedDict):
    name: str
    version: str
    source: t.NotRequired[PoetryLockfileV2Source]


# Must use the functional form of declaring TypedDicts
# because the keys are not valid Python identifiers.
PoetryLockfileV2Metadata = t.TypedDict(
    "PoetryLockfileV2Metadata",
    {
        "lock-version": str,
        "content-hash": str,
    },
)


@dataclass
class PoetryLockfileV2:
    # There is no official documentaton for this lockfile format.
    # The `Locker` class comes close:
    # <https://github.com/python-poetry/poetry/blob/1c059eadbb4c2bf29e01a61979b7f50263c9e506/src/poetry/packages/locker.py#L53>
    metadata: PoetryLockfileV2Metadata
    package: list[PoetryLockfileV2Package]


AnyLockfile = t.Annotated[
    UvLockfileV1 | PoetryLockfileV2, pydantic.Field(union_mode="left_to_right")
]

_ANY_LOCKFILE_SCHEMA = pydantic.TypeAdapter[AnyLockfile](AnyLockfile)


def _map_uv_source(source: UvLockfileV1Source) -> Source:
    match source:
        case {"registry": registry} if _is_pypi_url(registry):
            return "pypi"
        case {"registry": registry}:
            return SourceRegistry(registry)
        case {"url": url, "subdirectory": subdirectory}:
            return SourceDirect(url, subdirectory=subdirectory)
        case {"git": url}:
            return SourceDirect(_make_vcs_url_from_uv_direct_url("git", url))
        case {"url": url}:
            return SourceDirect(url)
        case {"path": url} | {"directory": url} | {"editable": url} | {"virtual": url}:
            return SourceDirect(url)
        case _:
            # TODO emit warning
            return "other"


def _map_poetry_source(source: PoetryLockfileV2Source | None) -> Source:
    if source is None:
        return "default"
    match source:
        case {"type": type} if type.lower() == "pypi":
            return "pypi"
        case {"type": "legacy", "url": url} if _is_pypi_url(url):
            return "pypi"
        case {"type": "legacy", "url": url}:
            return SourceRegistry(url)
        case {"type": "git", "url": url, "resolved_reference": hash}:
            return SourceDirect(
                _make_vcs_url(
                    "git", url, hash=hash, subdirectory=source.get("subdirectory")
                )
            )
        case {"type": "url", "url": url, "subdirectory": subdirectory}:
            return SourceDirect(url, subdirectory=subdirectory)
        case {"type": "directory" | "file" | "url", "url": url}:
            return SourceDirect(url)
        case _:
            # TODO emit warning
            return "other"


def _is_pypi_url(url: str) -> bool:
    return yarl.URL(url).host == "pypi.org"


def _make_vcs_url(
    vcs: t.Literal["git"], url: str, *, hash: str, subdirectory: str | None = None
) -> str:
    """Attach metadata to a VCS URL in a manner that Poetry, UV, and Pip understand.

    Poetry source: https://github.com/python-poetry/poetry-core/blob/6b67b60279ae0706bc2f4723075c6d810eac584c/src/poetry/core/vcs/git.py#L127
    Pip docs: https://pip.pypa.io/en/stable/topics/vcs-support/

    Examples of successful changes:

    >>> _make_vcs_url("git", "git://user@example.com/foo.git", hash="main")
    'git://user@example.com/foo.git@main'
    >>> _make_vcs_url(
    ...     "git",
    ...     "https://example.com/foo.git",
    ...     hash="1234abc",
    ...     subdirectory="some/path",
    ... )
    'git+https://example.com/foo.git@1234abc#subdirectory=some/path'

    Examples of rejected URLs:

    >>> _make_vcs_url("git", "user@example.com/foo.git", hash="main")
    Traceback (most recent call last):
    ValueError: ...
    >>> _make_vcs_url("git", "git+https://example.com", hash="main")
    Traceback (most recent call last):
    ValueError: ...
    >>> _make_vcs_url("git", "https://example.com/a@b", hash="main")
    Traceback (most recent call last):
    ValueError: ...
    >>> _make_vcs_url("git", "https://example.com/foo?a=b", hash="main")
    Traceback (most recent call last):
    ValueError: ...
    >>> _make_vcs_url("git", "https://example.com/foo#fragment", hash="main")
    Traceback (most recent call last):
    ValueError: ...

    """
    u = yarl.URL(url)

    err_msg = f"VCS URL cannot be edited safely: {url}"
    if not u.scheme:
        raise ValueError(err_msg)
    if "+" in u.scheme:
        raise ValueError(err_msg)
    if "@" in u.path:
        raise ValueError(err_msg)
    if u.query_string:
        raise ValueError(err_msg)
    if u.fragment:
        raise ValueError(err_msg)

    if u.scheme != vcs:
        u = u.with_scheme(f"{vcs}+{u.scheme}")

    u = u.with_path(f"{u.path}@{hash}")

    if subdirectory:
        u = u.with_fragment(f"subdirectory={subdirectory}")

    return str(u)


def _make_vcs_url_from_uv_direct_url(vcs: t.Literal["git"], direct_url: str) -> str:
    """Fix up uv's custom format for direct Git URLs.

    Example of correcting an URL:

    >>> _make_vcs_url_from_uv_direct_url(
    ...     "git", "https://example.com/foo.git?subdirectory=a/b&branch=main#abcd123"
    ... )
    'git+https://example.com/foo.git@abcd123#subdirectory=a/b'

    Example of rejected URL:

    >>> _make_vcs_url_from_uv_direct_url(
    ...     "git", "https://example.com/foo.git?subdirectory=a/b"
    ... )
    Traceback (most recent call last):
    ValueError: ...

    """
    u = yarl.URL(direct_url)
    err_msg = f"VCS URL cannot be edited safely: {direct_url}"

    # Extract available information from the Direct URL as per
    # https://github.com/astral-sh/uv/blob/141369ce73b7b0b4e005b0f45107d13c828a99e0/crates/uv-resolver/src/lock/mod.rs#L3907-L3920
    #
    # Other parts of the uv source code do related URL manipulation:
    # https://github.com/astral-sh/uv/blob/141369ce73b7b0b4e005b0f45107d13c828a99e0/crates/uv-git-types/src/lib.rs#L102-L152
    # https://github.com/astral-sh/uv/blob/141369ce73b7b0b4e005b0f45107d13c828a99e0/crates/uv-pypi-types/src/direct_url.rs#L127-L136
    # https://github.com/astral-sh/uv/blob/141369ce73b7b0b4e005b0f45107d13c828a99e0/crates/uv-pypi-types/src/parsed_url.rs#L280-L299
    # https://github.com/astral-sh/uv/blob/141369ce73b7b0b4e005b0f45107d13c828a99e0/crates/uv-pypi-types/src/parsed_url.rs#L480-L492

    # First, extract the most precise revision information.
    rev = ""
    for key in ("branch", "tag", "rev"):
        rev = u.query.get(key, rev)
    rev = u.fragment or rev
    if not rev:
        raise ValueError(err_msg)

    # Next, extract subdirectory info.
    subdirectory = u.query.get("subdirectory")

    # Remove any parsed parts from the URL.
    u = u.with_fragment("")
    u = u.with_query("")

    # Finally, reconstruct the proper URL.
    return _make_vcs_url(vcs, str(u), hash=rev, subdirectory=subdirectory)
