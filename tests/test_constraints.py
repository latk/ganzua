# TODO test semver idioms with 0.x versions

from ganzua import Lockfile
from ganzua._constraints import (
    Requirement,
    UnconstrainRequirement,
    UpdateRequirement,
    parse_requirement_from_pep508,
)

_LOCKFILE: Lockfile = {
    "packages": {
        "foo": {"version": "7.1.2"},
        "minor": {"version": "4.5.6"},
    },
}


def _assert_updated_req(input: str, expected: str) -> None:
    __tracebackhide__ = True  # better Pytest errors
    req = parse_requirement_from_pep508(input)
    UpdateRequirement(_LOCKFILE).apply(req, kind="pep508")
    # TODO compare normalized form
    assert req == parse_requirement_from_pep508(expected)


def _assert_updated_poetry_req(name: str, input: str, expected: str) -> None:
    __tracebackhide__ = True
    req = Requirement(name=name, specifier=input)
    UpdateRequirement(_LOCKFILE).apply(req, kind="poetry")
    assert req == Requirement(name=name, specifier=expected)


def _assert_unconstrained_req(input: str, expected: str) -> None:
    __tracebackhide__ = True
    req = parse_requirement_from_pep508(input)
    UnconstrainRequirement().apply(req, kind="pep508")
    # TODO compare normalized form
    assert req == parse_requirement_from_pep508(expected)


def test_update_requirement_not_found() -> None:
    _assert_updated_req("bar >=4,<5", "bar >=4,<5")  # unchanged
    _assert_updated_poetry_req("bar", "^4", "^4")  # unchanged


def test_update_requirement_unconstrainted() -> None:
    _assert_updated_req("foo", "foo")
    _assert_updated_poetry_req("foo", "*", "*")


def test_update_requirement_major_lower_bound() -> None:
    _assert_updated_req("foo >=4", "foo >=7")
    _assert_updated_req("foo >=4.3", "foo >=7.1")
    _assert_updated_req("foo >=4.3.2", "foo >=7.1.2")
    _assert_updated_poetry_req("foo", ">=4.3", ">=7.1")


def test_update_requirement_minor_lower_bound() -> None:
    _assert_updated_req("minor >=4", "minor >=4")
    _assert_updated_req("minor >=4.3", "minor >=4.5")
    _assert_updated_req("minor >=4.3.2", "minor >=4.5.6")
    _assert_updated_poetry_req("minor", ">=4.3", ">=4.5")


def test_update_requirement_semver_idiom() -> None:
    # One semver idiom uses exclusive upper bounds.
    _assert_updated_req("foo >=4,<5", "foo >=7,<8")
    _assert_updated_req("foo >=4.3,<5", "foo >=7.1,<8")
    _assert_updated_req("foo >=4.3.2,<5", "foo >=7.1.2,<8")
    _assert_updated_req("foo >=7.0.1,<8", "foo >=7.1.2,<8")  # bump lower bound
    _assert_updated_req("foo >=7.9.9,<8", "foo >=7.1.2,<8")  # downgraded!
    _assert_updated_req("foo >=4.3,<10", "foo >=7.1,<10")  # upper bound not changed

    # The other semver idiom uses `>=X.Y,==X.*`.
    _assert_updated_req("foo >=4,==4.*", "foo >=7,==7.*")
    _assert_updated_req("foo >=4.3,==4.*", "foo >=7.1,==7.*")
    _assert_updated_req("foo >=4.3.2,==4.*", "foo >=7.1.2,==7.*")
    _assert_updated_req("foo >=7.0.1,==7.*", "foo >=7.1.2,==7.*")
    _assert_updated_req("foo >=7.9.9,==7.*", "foo >=7.1.2,==7.*")  # downgraded!


def test_update_requirement_poetry_semver() -> None:
    _assert_updated_poetry_req("foo", "^4", "^7")
    _assert_updated_poetry_req("foo", "^4.3", "^7.1")
    _assert_updated_poetry_req("foo", "^4.3.2", "^7.1.2")
    _assert_updated_poetry_req("foo", "^7.0.1", "^7.1.2")
    _assert_updated_poetry_req("foo", "^7.9.9", "^7.1.2")  # downgraded!


def test_update_requirement_compatible() -> None:
    """Compatible release constraints are sensitive to the version granularity."""
    _assert_updated_req("foo ~=4.3", "foo ~=7.1")
    _assert_updated_req("foo ~=4.3.2", "foo ~=7.1.2")
    _assert_updated_req("foo ~=7.1", "foo ~=7.1")
    _assert_updated_req("foo ~=7.1.2", "foo ~=7.1.2")
    _assert_updated_req("foo ~=7.9", "foo ~=7.1")  # downgrade
    _assert_updated_req("foo ~=8.9", "foo ~=7.1")  # downgrade
    _assert_updated_req("foo ~=7.0", "foo ~=7.1")  # explicit zeroes count
    _assert_updated_req("foo ~=7.1.0", "foo ~=7.1.2")  # explicit zeroes count


def test_update_requirement_poetry_compatible() -> None:
    _assert_updated_poetry_req("foo", "~4.3", "~7.1")
    _assert_updated_poetry_req("foo", "~4.3.2", "~7.1.2")
    _assert_updated_poetry_req("foo", "~7.1", "~7.1")
    _assert_updated_poetry_req("foo", "~7.1.2", "~7.1.2")
    _assert_updated_poetry_req("foo", "~7.9", "~7.1")  # downgrade
    _assert_updated_poetry_req("foo", "~8.9", "~7.1")  # downgrade


def test_update_requirement_exact() -> None:
    """Exact requirements are replaced with the full version number."""
    _assert_updated_req("foo ==4.3.2", "foo ==7.1.2")
    _assert_updated_req("foo ==4.3", "foo ==7.1.2")
    _assert_updated_req("foo ==4", "foo ==7.1.2")
    _assert_updated_req("foo ==7", "foo ==7.1.2")
    _assert_updated_req("foo ==7.1", "foo ==7.1.2")
    _assert_updated_req("foo ==7.1.2", "foo ==7.1.2")  # no change


def test_update_requirement_prefix() -> None:
    """Updated prefix constraints match granularity."""
    _assert_updated_req("foo ==4.*", "foo ==7.*")
    _assert_updated_req("foo ==4.3.*", "foo ==7.1.*")
    _assert_updated_req("foo ==7.*", "foo ==7.*")
    _assert_updated_req("foo ==7.0.*", "foo ==7.1.*")
    _assert_updated_req("foo ==7.*", "foo ==7.*")  # no change
    _assert_updated_req("foo ==7.1.*", "foo ==7.1.*")  # no change


def test_update_requirement_poetry_exact() -> None:
    _assert_updated_poetry_req("foo", "4.3.2", "7.1.2")
    _assert_updated_poetry_req("foo", "4.3", "7.1.2")
    _assert_updated_poetry_req("foo", "4", "7.1.2")
    _assert_updated_poetry_req("foo", "7", "7.1.2")
    _assert_updated_poetry_req("foo", "7.1", "7.1.2")
    _assert_updated_poetry_req("foo", "7.1.2", "7.1.2")  # no change


def test_update_requirement_poetry_prefix() -> None:
    _assert_updated_poetry_req("foo", "4.*", "7.*")
    _assert_updated_poetry_req("foo", "4.3.*", "7.1.*")
    _assert_updated_poetry_req("foo", "7.*", "7.*")
    _assert_updated_poetry_req("foo", "7.0.*", "7.1.*")
    _assert_updated_poetry_req("foo", "7.*", "7.*")  # no change
    _assert_updated_poetry_req("foo", "7.1.*", "7.1.*")  # no change


def test_update_requirement_exclusion() -> None:
    # most exclusions are kept as they don't affect the current version
    _assert_updated_req("foo !=4.3.2", "foo !=4.3.2")
    _assert_updated_req("foo !=4.*", "foo !=4.*")
    _assert_updated_req("foo !=7.9.*", "foo !=7.9.*")
    _assert_updated_req("foo !=7.0.1", "foo !=7.0.1")

    # exclusions are removed if they match the current version 7.3.2
    _assert_updated_req("foo !=7.*", "foo")
    _assert_updated_req("foo !=7.1.*", "foo")
    _assert_updated_req("foo !=7.1.2", "foo")


def test_update_requirement_exclusive_bounds() -> None:
    _assert_updated_req("foo >4", "foo >4")
    _assert_updated_req("foo >8", "foo")
    _assert_updated_req("foo <5", "foo")
    _assert_updated_req("foo <8", "foo <8")


def test_update_requirement_arbitrary_equality() -> None:
    _assert_updated_req("foo ===4.3.2", "foo")
    _assert_updated_req("foo ===7.1.2", "foo===7.1.2")


def test_unconstrain_requirement() -> None:
    _assert_unconstrained_req("foo", "foo")
    _assert_unconstrained_req("foo >4,<=5,!=4.3.7", "foo")


def test_unconstrain_requirement_poetry() -> None:
    req = Requirement(name="foo", specifier="^1.2.3")
    UnconstrainRequirement().apply(req, kind="poetry")
    assert req == Requirement(name="foo", specifier="*")
