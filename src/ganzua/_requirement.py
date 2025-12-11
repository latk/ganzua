import re
import typing as t
from dataclasses import dataclass

import pydantic
from packaging.markers import Marker
from packaging.requirements import Requirement as Pep508Requirement
from pydantic_core import core_schema


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
    """A resolver-agnostic Requirement model.

    This corresponds to one dependency entry in a `pyproject.toml` file.
    This is a lexical/textual concept about information in the file,
    intended for inspection and edits.

    Requirements can be difficult to interpret.
    There might be multiple Requirements that point to the same package,
    potentially with complementary or contradictory contents.
    Features like `[dependency-groups]` or `[tool.poetry.extras]`
    can include the same Requirement in multiple places,
    which is why the `groups` and `in_extras` fields may have multiple values.
    """

    name: Name
    """The name of the required package."""

    specifier: str
    """Version specifier for the required package, may use PEP-508 or Poetry syntax."""

    extras: t.NotRequired[frozenset[Name]]
    """Extras enabled for the required package."""

    marker: t.NotRequired[t.Annotated[Marker, FromToString]]
    """Environment marker expression describing when this requirement should be installed."""

    groups: t.NotRequired[frozenset[Name]]
    """Dependency groups that this requirement is part of."""

    in_extras: t.NotRequired[frozenset[Name]]
    """Extras that this optional requirement is part of.

    Requirements can only be part of one extra (with some exceptions).

    The `groups` and `in_extras` fields are effectively mutually exclusive.

    Special cases for legacy Poetry:

    * When using `[tool.poetry.extras]`, one requirement can be part of multiple extras.
    * The `marker` might also reference extras.
    """

    # TODO instead of directly supporting URLs,
    # should develop a more general concept of sources.
    # url: t.NotRequired[str]
    # """URL for an URL-dependency."""


class Requirements(t.TypedDict):
    requirements: t.Sequence[Requirement]


def parse_requirement_from_pep508(
    req: Pep508Requirement | str,
    *,
    groups: frozenset[Name] = frozenset(),
    in_extra: Name | None = None,
) -> Requirement:
    if isinstance(req, str):
        req = Pep508Requirement(req)
    data = Requirement(name=normalized_name(req.name), specifier=str(req.specifier))
    if req.extras:
        data["extras"] = frozenset(normalized_name(n) for n in req.extras)
    if req.marker:
        data["marker"] = req.marker
    if groups:
        data["groups"] = groups
    if in_extra is not None:
        data["in_extras"] = frozenset([in_extra])
    return data
