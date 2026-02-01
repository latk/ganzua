# TODO test semver idioms with 0.x versions

from ganzua._edit_requirement import UnconstrainRequirement
from ganzua._requirement import (
    RequirementWithKind,
    assert_normalized_name,
    parse_requirement_from_pep508,
)


def _assert_unconstrained_req(input: str, expected: str) -> None:
    __tracebackhide__ = True
    req = parse_requirement_from_pep508(input)
    UnconstrainRequirement().apply(req)
    # TODO compare normalized form
    assert req == parse_requirement_from_pep508(expected)


def test_unconstrain_requirement() -> None:
    _assert_unconstrained_req("foo", "foo")
    _assert_unconstrained_req("foo >4,<=5,!=4.3.7", "foo")


def test_unconstrain_requirement_poetry() -> None:
    req = RequirementWithKind(
        name=assert_normalized_name("foo"), specifier="^1.2.3", kind="poetry"
    )
    UnconstrainRequirement().apply(req)
    assert req == RequirementWithKind(
        name=assert_normalized_name("foo"), specifier="*", kind="poetry"
    )
