import copy
import typing as t
from dataclasses import dataclass

import pydantic
from packaging.requirements import Requirement as Pep508Requirement
from packaging.specifiers import Specifier, SpecifierSet
from packaging.utils import canonicalize_version
from packaging.version import Version

from ._lockfile import Lockfile


@dataclass(frozen=True, slots=True)
class PoetryRequirement:
    name: str
    specifier: str


@pydantic.with_config(use_attribute_docstrings=True)
class Requirement(t.TypedDict):
    # compare: https://github.com/pypa/packaging/blob/e9b9d09ebc5992ecad1799da22ee5faefb9cc7cb/src/packaging/requirements.py#L21
    """A resolver-agnostic Requirement model."""

    name: str
    """The name of the required package."""
    specifier: str
    """Version specifier for the required package, may use PEP-508 or Poetry syntax."""
    url: t.NotRequired[str]
    """URL for an URL-dependency."""
    extras: t.NotRequired[frozenset[str]]
    """Extras enabled for the required package."""
    marker: t.NotRequired[str]
    """Environment marker expression describing when this requirement should be installed."""
    groups: t.NotRequired[frozenset[str]]
    """Dependency groups that this requirement is part of."""


class Requirements(t.TypedDict):
    requirements: t.Sequence[Requirement]


REQUIREMENTS_SCHEMA = pydantic.TypeAdapter(Requirements)


def _requirement_from_pep508(
    req: Pep508Requirement,  # *, groups: frozenset[str] = frozenset()
) -> Requirement:
    return Requirement(name=req.name, specifier=str(req.specifier))
    # TODO support additional fields
    # if req.url:
    #     data["url"] = req.url
    # if req.extras:
    #     data["extras"] = frozenset(req.extras)
    # if req.marker:
    #     data["marker"] = str(req.marker)
    # if groups:
    #     data["groups"] = groups
    # return data


def _requirement_from_poetry(
    req: PoetryRequirement,  # *, groups: frozenset[str] = frozenset()
) -> Requirement:
    return Requirement(name=req.name, specifier=req.specifier)


class MapRequirement(t.Protocol):  # pragma: no cover
    def pep508(self, req: Pep508Requirement) -> Pep508Requirement: ...
    def poetry(self, req: PoetryRequirement) -> PoetryRequirement: ...


@dataclass
class UpdateRequirement(MapRequirement):
    """Update a requirement constraint to match the locked version."""

    lockfile: Lockfile

    @t.override
    def pep508(self, req: Pep508Requirement) -> Pep508Requirement:
        target = self.lockfile.get(req.name)
        if not target:
            return req

        target_version = Version(target["version"])
        updated_specifier = _update_specifier_set(req.specifier, target_version)
        if req.specifier == updated_specifier:
            return req

        updated = copy.copy(req)
        updated.specifier = _PrettySpecifierSet(updated_specifier)
        return updated

    @t.override
    def poetry(self, req: PoetryRequirement) -> PoetryRequirement:
        target = self.lockfile.get(req.name)
        if not target:
            return req

        target_version = Version(target["version"])
        updated_specifier = _update_poetry_specifier(req.specifier, target_version)
        if req.specifier == updated_specifier:
            return req

        return PoetryRequirement(req.name, updated_specifier)


@dataclass
class UnconstrainRequirement(MapRequirement):
    @t.override
    def pep508(self, req: Pep508Requirement) -> Pep508Requirement:
        """Remove any constraints from the requirement."""
        if not req.specifier:
            return req

        updated = copy.copy(req)
        updated.specifier = SpecifierSet()
        return updated

    @t.override
    def poetry(self, req: PoetryRequirement) -> PoetryRequirement:
        return PoetryRequirement(name=req.name, specifier="*")


@dataclass
class CollectRequirement(MapRequirement):
    """Collect all requirements into an array, without changing them."""

    reqs: list[Requirement]

    @t.override
    def pep508(self, req: Pep508Requirement) -> Pep508Requirement:
        self.reqs.append(_requirement_from_pep508(req))
        return req

    @t.override
    def poetry(self, req: PoetryRequirement) -> PoetryRequirement:
        self.reqs.append(_requirement_from_poetry(req))
        return req


def _update_poetry_specifier(spec: str, target: Version) -> str:
    """Update a Poetry version specifier.

    Poetry supports both PEP-440 constraints,
    as well as a couple of operators of its own.
    Cf https://python-poetry.org/docs/dependency-specification/#version-constraints
    """
    # unconstrained
    if spec.strip() == "*":
        return spec

    # ordinary PEP-440 specifier
    if spec.startswith(("<", ">", "==", "!=", "~=")):
        return _update_poetry_specifier_translated(
            spec, target, poetry_operator="", pep440_operator=""
        )

    # Poetry semver constraint
    if spec.startswith("^"):
        return _update_poetry_specifier_translated(
            spec, target, poetry_operator="^", pep440_operator=">="
        )

    # Poetry compatibility constraint
    if spec.startswith("~"):
        return _update_poetry_specifier_translated(
            spec, target, poetry_operator="~", pep440_operator="~="
        )

    # bare numbers are treated as `==` specifiers (exact or prefix)
    return _update_poetry_specifier_translated(
        spec, target, poetry_operator="", pep440_operator="=="
    )


def _update_poetry_specifier_translated(
    spec: str, target: Version, *, poetry_operator: str, pep440_operator: str
) -> str:
    old_spec = SpecifierSet(pep440_operator + spec.removeprefix(poetry_operator))
    new_spec = _update_specifier_set(old_spec, target)
    if old_spec == new_spec:
        return spec
    return poetry_operator + str(new_spec).removeprefix(pep440_operator)


def _update_specifier_set(spec: SpecifierSet, target: Version) -> SpecifierSet:
    """Update a specifier set to match the target version."""
    # TODO fall back to lower bound
    updated_spec = SpecifierSet(
        updated for s in spec if (updated := _update_specifier(s, target))
    )
    if _is_semver_idiom(spec) and not spec.contains(target):
        updated_spec = SpecifierSet(
            [
                *updated_spec,
                Specifier(f"<{target.major + 1}"),
            ]
        )
    return updated_spec


def _update_specifier(  # noqa: PLR0911  # too-many-return-statements
    spec: Specifier, target: Version
) -> Specifier | None:
    """Upgrade the specifier to the target version, matching granularity.

    If the target doesn't match, return `None`.

    The semantics of version specifiers are explained in:
    <https://packaging.python.org/en/latest/specifications/version-specifiers/>
    """
    match spec.operator:
        case "!=" | "<" | ">" | "<=" | "===":
            # Can't reliably change these constraints.
            # Return them if they are still valid, else discard.
            if spec.contains(target):
                return spec
            return None

        case "==" if spec.version.endswith(".*"):  # prefix match
            current_prefix = spec.version.removesuffix(".*")
            target_prefix = _granularity_matched_version(
                target, template=Version(current_prefix)
            )
            if target_prefix == current_prefix:
                return spec
            return Specifier(f"{spec.operator}{target_prefix}.*")

        case "==":  # exact match
            if canonicalize_version(target) == canonicalize_version(spec.version):
                return spec  # no change needed
            return Specifier(f"=={target}")

        case "~=" | ">=":
            current = Version(spec.version)
            if canonicalize_version(target) == canonicalize_version(current):
                return spec  # no change needed
            truncated_target = _granularity_matched_version(target, template=current)
            return Specifier(f"{spec.operator}{truncated_target}")

        case other:  # pragma: no cover
            raise ValueError(f"unknown specifier operator {other!r}")


def _granularity_matched_version(version: Version, *, template: Version) -> str:
    # TODO support epoch
    # TODO support granularity matching incl pre/post/dev
    granularity = len(template.base_version.split("."))
    return ".".join(version.base_version.split(".")[:granularity])


def _is_semver_idiom(spec: SpecifierSet) -> bool:
    """Check for patterns like `>=2.1,<3`.

    We need this to potentially restore an invalidated upper bound.
    The other semver idiom looks like `>=2.1,==2.*`, which works directly.
    """
    lower = [Version(s.version) for s in spec if s.operator == ">="]
    upper = [Version(s.version) for s in spec if s.operator == "<"]
    match lower, upper:
        case [lo], [hi] if lo < hi and lo.major < hi.major:
            return True
        case _:
            return False


class _PrettySpecifierSet(SpecifierSet):
    """Override a SpecifierSet to emit specifiers in a prettier order.

    >>> str(_PrettySpecifierSet("<5,>=4"))
    '>=4,<5'
    """

    @t.override
    def __iter__(self) -> t.Iterator[Specifier]:
        # cf https://github.com/pypa/packaging/blob/0055d4b8ff353455f0617690e609bc68a1f9ade2/src/packaging/specifiers.py#L852
        return iter(sorted(super().__iter__(), key=_specifier_sort_key))

    @t.override
    def __str__(self) -> str:
        # cf https://github.com/pypa/packaging/blob/0055d4b8ff353455f0617690e609bc68a1f9ade2/src/packaging/specifiers.py#L775
        return ",".join(str(s) for s in self)


_SPECIFIER_OPERATOR_RANK: t.Final = (">", ">=", "~=", "==", "<=", "<", "!=", "===")


def _specifier_sort_key(spec: Specifier) -> tuple[int, str]:
    """Determine a total order over specifiers, instead of relying on unspecified hash.

    >>> _specifier_sort_key(Specifier(">=4"))
    (1, '4')
    >>> _specifier_sort_key(Specifier("<5"))
    (5, '5')
    >>> _specifier_sort_key(Specifier(">=4")) < _specifier_sort_key(Specifier("<5"))
    True
    """
    try:
        operator_rank = _SPECIFIER_OPERATOR_RANK.index(spec.operator)
    except ValueError:  # pragma: no cover
        operator_rank = 999
    return operator_rank, spec.version
