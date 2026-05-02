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
    name: str
    """Name of the package.

    *Added in Ganzua 0.4.0:* previously, the package name was implicit.
    """

    version: str
    source: Source


@pydantic.with_config(use_attribute_docstrings=True)
class Lockfile(t.TypedDict):
    packages: list[LockedPackage]
    """All packages in the lockfile.

    In case of split versions, there can be multiple entries with the same package name.

    *Changed in Ganzua 0.4.0:* `packages` is now a list.
    Previously, it was a `name → LockedPackage` table.
    """


LockfileByName = t.NewType("LockfileByName", dict[str, list[LockedPackage]])


def lockfile_from(path: PathLike) -> Lockfile:
    with error_context(f"while parsing {path}"):
        input_lockfile = _ANY_LOCKFILE_SCHEMA.validate_python(
            tomllib.loads(path.read_text())
        )

        match input_lockfile:
            case UvLockfileV1(package=uv_packages):
                packages = [
                    LockedPackage(
                        name=p["name"],
                        version=p.get("version", UNDEFINED_VERSION),
                        source=_map_uv_source(p["source"]),
                    )
                    for p in uv_packages
                ]
            case PoetryLockfileV2(package=poetry_packages):
                packages = [
                    LockedPackage(
                        name=p["name"],
                        version=p["version"],
                        source=_map_poetry_source(p.get("source")),
                    )
                    for p in poetry_packages
                ]
            case PylockV1(packages=pylock_packages):
                packages = [
                    LockedPackage(
                        name=p["name"],
                        version=p.get("version", UNDEFINED_VERSION),
                        source=_map_pylock_source(p),
                    )
                    for p in pylock_packages
                ]
            case other:
                t.assert_never(other)

    return Lockfile(packages=sorted(packages, key=lambda p: (p["name"], p["version"])))


class UvLockfileV1Source(t.TypedDict, total=False):
    """Package source information as locked by uv.

    Only ONE field may be set (or `url` + `subdirectory`).

    The lockfile sources do not match the [`[tool.uv.sources]` syntax](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-sources).
    Instead, the possible sources are defined in the [uv-resolver `SourceWire` enum](https://github.com/astral-sh/uv/blob/141369ce73b7b0b4e005b0f45107d13c828a99e0/crates/uv-resolver/src/lock/mod.rs#L3736).
    """

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
    """Package information as locked by uv.

    Ganzua ignores details such as hashes or wheels.
    """

    name: str
    """The name of the package."""
    version: t.NotRequired[str]
    """The locked version of the package.
    Note that some packages don't have a version."""
    source: UvLockfileV1Source
    """Where this package was obtained from.
    Uv provides this information for *every* package."""


@dataclass
class UvLockfileV1:
    """The uv lockfile format (v1).

    Documentation: <https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile>

    There is no specification for this schema by uv/Astral.
    However, uv promises [some compatibility guarantees](https://docs.astral.sh/uv/concepts/resolution/#lockfile-versioning).
    Therefore, we pin this model to only match the v1.x schema.
    Future changes will get their own model.
    """

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
    """Package information as locked by Poetry."""

    name: str
    version: str
    source: t.NotRequired[PoetryLockfileV2Source]


# Must use the functional form of declaring TypedDicts
# because the keys are not valid Python identifiers.
PoetryLockfileV2Metadata = t.TypedDict(
    "PoetryLockfileV2Metadata",
    {
        "lock-version": t.Annotated[
            str,
            pydantic.Field(
                description="""\
Version of the Poetry lockfile format.

At the time of writing, the lockfile format version is at `2.1`.
Ganzua doesn't validate this, and accepts any string for now.
"""
            ),
        ],
        "content-hash": t.Annotated[
            str,
            pydantic.Field(
                description="""\
Poetry hashes a canonical version of all requirements and stores it in the lockfile.

Ganzua requires the presence of this field, but does not validate the contents in any way.
"""
            ),
        ],
    },
)


@dataclass
class PoetryLockfileV2:
    """The Poetry lockfile format (v2).

    There is no official documentation for this lockfile format.
    The [`Locker` class](https://github.com/python-poetry/poetry/blob/1c059eadbb4c2bf29e01a61979b7f50263c9e506/src/poetry/packages/locker.py#L53) comes close.
    """

    metadata: PoetryLockfileV2Metadata
    """Metadata block for the lockfile.
    Ganzua doesn't actively use this information, other than to distinguish lockfile formats from each other.
    """

    package: list[PoetryLockfileV2Package]


class PylockV1Vcs(t.TypedDict, total=False):
    """Package source for `pylock.toml` files indicating a version control system.

    Either `url` or `path` must be present.
    """

    type: t.Required[t.Literal["git"] | str]
    """A Registered VCS name. In practice, `git` is the only meaningful value.

    Spec: <https://packaging.python.org/en/latest/specifications/direct-url-data-structure/#direct-url-data-structure-registered-vcs>
    """
    url: str
    path: str
    requested_revision: str
    commit_id: t.Required[str]
    subdirectory: str


class PylockV1Directory(t.TypedDict, total=False):
    """Package source for `pylock.toml` files indicating a local directory."""

    path: t.Required[str]
    editable: bool
    """Treat as `False` if absent."""
    subdirectory: str


class PylockV1Archive(t.TypedDict, total=False):
    """Package source for `pylock.toml` files indicating an archive file.

    Either `url` or `path` must be present.

    The `size`, `upload-time`, and `hashes` fields are intentionally omitted.
    """

    url: str
    path: str
    subdirectory: str


class PylockV1Package(t.TypedDict, total=False):
    """Information about a single package in a `pylock.toml` file.

    We only extract the subset of relevant fields.
    Some fields are intentionally omitted:
    `marker`, `requires-python`, `dependencies`, `sdist`, `wheels`, `attestation-identities`.

    The `vcs`, `directory` and `archive` fields are mutually exclusive.
    """

    name: t.Required[str]
    """Name of the package, guaranteed to already be normalized."""

    version: str
    """Optional locked version."""

    vcs: PylockV1Vcs
    directory: PylockV1Directory
    archive: PylockV1Archive
    index: str
    """URL of the package index where wheels/sdists were locked from."""


@pydantic.with_config(
    alias_generator=lambda name: name.replace("_", "-"), use_attribute_docstrings=True
)
@dataclass
class PylockV1:
    """Relevant parts of the `pylock.toml` file format.

    Specification: <https://packaging.python.org/en/latest/specifications/pylock-toml/#file-format>
    """

    lock_version: t.Literal["1.0"] | str
    """Ganzua only supports version `1.0` (the currently specification)."""

    packages: list[PylockV1Package]


AnyLockfile = t.Annotated[
    UvLockfileV1 | PoetryLockfileV2 | PylockV1,
    pydantic.Field(
        union_mode="left_to_right",
        description="""\
Ganzua supports the `uv.lock`, `poetry.lock`, and `pylock.toml` lockfile formats.

The names of the files are ignored.
Instead, the supported format is sniffed from the contents of each lockfile.
""",
    ),
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


def _map_pylock_source(p: PylockV1Package) -> Source:
    match p:
        case {"vcs": {"type": "git", "url": url}}:
            return SourceDirect(
                _make_vcs_url(
                    "git",
                    url,
                    hash=p["vcs"]["commit_id"],
                    subdirectory=p["vcs"].get("subdirectory"),
                )
            )
        case {"directory": {"path": direct}}:
            return SourceDirect(direct, subdirectory=p["directory"].get("subdirectory"))
        case {"archive": {"url": direct} | {"path": direct}}:
            return SourceDirect(direct, subdirectory=p["archive"].get("subdirectory"))
        case {"vcs": _} | {"directory": _} | {"archive": _}:
            # TODO emit warning
            return "other"
        case {"index": url} if _is_pypi_url(url):
            return "pypi"
        case {"index": url}:
            return SourceRegistry(url)
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


def lockfile_by_name(lockfile: Lockfile) -> LockfileByName:
    by_name: dict[str, list[LockedPackage]] = {}
    for p in lockfile["packages"]:
        by_name.setdefault(p["name"], []).append(p)
    return LockfileByName(by_name)
