import re
import typing as t
from dataclasses import dataclass

import pydantic
from packaging.markers import Marker
from packaging.requirements import Requirement as Pep508Requirement
from packaging.specifiers import Specifier, SpecifierSet
from packaging.utils import canonicalize_version
from packaging.version import Version
from pydantic_core import core_schema

from ._lockfile import Lockfile


@dataclass
class FromToString:
    """Pydantic annotation to serialize the contents as a string."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[t.Any], _handler: pydantic.GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.union_schema(
            [
                core_schema.is_instance_schema(source),
                core_schema.no_info_after_validator_function(
                    source, core_schema.str_schema()
                ),
            ],
            serialization=core_schema.to_string_ser_schema(),
        )


Name = t.NewType("Name", str)
"""A normalized name, e.g. for dependencies, extras, or groups."""


def normalized_name(name: str) -> Name:
    """Convert the Name to its canonical form.

    See: <https://packaging.python.org/en/latest/specifications/name-normalization/>

    >>> normalized_name("Friendly_Bard")
    'friendly-bard'
    """
    return Name(re.sub(r"[-_.]+", "-", name).lower())


def assert_normalized_name(name: str) -> Name:
    """Checked cast to a `Name`, without performing normalization.

    Raises `ValueError` upon failure.

    >>> assert_normalized_name("foo-bar")
    'foo-bar'
    >>> assert_normalized_name("Foo.Bar")
    Traceback (most recent call last):
    ValueError: name is not normalized: 'Foo.Bar'
    """
    if name == normalized_name(name):
        return Name(name)
    msg = f"name is not normalized: {name!r}"
    raise ValueError(msg)


@pydantic.with_config(use_attribute_docstrings=True)
class Requirement(t.TypedDict):
    # compare: https://github.com/pypa/packaging/blob/e9b9d09ebc5992ecad1799da22ee5faefb9cc7cb/src/packaging/requirements.py#L21
    """A resolver-agnostic Requirement model."""

    name: str
    """The name of the required package."""
    specifier: str
    """Version specifier for the required package, may use PEP-508 or Poetry syntax."""
    extras: t.NotRequired[frozenset[str]]
    """Extras enabled for the required package."""
    marker: t.NotRequired[t.Annotated[Marker, FromToString]]
    """Environment marker expression describing when this requirement should be installed."""
    groups: t.NotRequired[frozenset[Name]]
    """Dependency groups that this requirement is part of."""

    # TODO instead of directly supporting URLs,
    # should develop a more general concept of sources.
    # url: t.NotRequired[str]
    # """URL for an URL-dependency."""


class Requirements(t.TypedDict):
    requirements: t.Sequence[Requirement]


REQUIREMENTS_SCHEMA = pydantic.TypeAdapter(Requirements)


def parse_requirement_from_pep508(
    req: Pep508Requirement | str,
    *,
    groups: frozenset[Name] = frozenset(),
) -> Requirement:
    if isinstance(req, str):
        req = Pep508Requirement(req)
    data = Requirement(name=req.name, specifier=str(req.specifier))
    if req.extras:
        data["extras"] = frozenset(req.extras)
    if req.marker:
        data["marker"] = req.marker
    if groups:
        data["groups"] = groups
    return data


Kind = t.Literal["pep508", "poetry"]


class EditRequirement(t.Protocol):  # pragma: no cover
    def apply(self, req: Requirement, *, kind: Kind) -> None: ...


@dataclass
class UpdateRequirement(EditRequirement):
    """Update a requirement constraint to match the locked version."""

    lockfile: Lockfile

    @t.override
    def apply(self, req: Requirement, *, kind: Kind) -> None:
        target = self.lockfile["packages"].get(req["name"])
        if not target:
            return
        target_version = Version(target["version"])

        match kind:
            case "pep508":
                old_specifier = SpecifierSet(req["specifier"])
                updated_specifier = _update_specifier_set(old_specifier, target_version)
                if old_specifier == updated_specifier:
                    return

                req["specifier"] = str(updated_specifier)

            case "poetry":
                updated_poetry_specifier = _update_poetry_specifier(
                    req["specifier"], target_version
                )
                if req["specifier"] == updated_poetry_specifier:
                    return

                req["specifier"] = updated_poetry_specifier

            case other:  # pragma: no cover
                t.assert_never(other)


@dataclass
class UnconstrainRequirement(EditRequirement):
    """Remove any constraints from the requirement."""

    @t.override
    def apply(self, req: Requirement, *, kind: Kind) -> None:
        match kind:
            case "pep508":
                req["specifier"] = ""
            case "poetry":
                req["specifier"] = "*"
            case other:  # pragma: no cover
                t.assert_never(other)


@dataclass
class SetMinimumRequirement(EditRequirement):
    """Set the constraints to the minimum locked version."""

    lockfile: Lockfile

    @t.override
    def apply(self, req: Requirement, *, kind: Kind) -> None:
        target = self.lockfile["packages"].get(req["name"])
        if not target:
            return
        req["specifier"] = f">={target['version']}"


@dataclass
class CollectRequirement(EditRequirement):
    """Collect all requirements into an array, without changing them."""

    reqs: list[Requirement]

    @t.override
    def apply(self, req: Requirement, *, kind: Kind) -> None:
        self.reqs.append(req)


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
