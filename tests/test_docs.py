import importlib.metadata
import pathlib
import re

import pytest
from inline_snapshot import external_file

from ganzua import UpdateRequirement
from ganzua._doctest import Runner
from ganzua._pyproject import apply_one_pep508_edit

from . import resources

_GANZUA_VERSION = importlib.metadata.version("ganzua")


def test_readme() -> None:
    """Test to ensure that the README is up to date.

    * matches current `ganzua help`
    * all doctests produce expected output
    """
    readme = Runner.run(resources.README)
    readme = _bump_mentioned_versions(readme)
    assert readme == external_file(str(resources.README), format=".txt")


@pytest.mark.parametrize(
    "path",
    resources.DOCS.glob("**/*.md"),
    ids=lambda p: str(p.relative_to(resources.DOCS)),
)
def test_docs(path: pathlib.Path) -> None:
    markdown = Runner.run(path)
    assert markdown == external_file(str(path), format=".txt")


def test_changelog_mentions_current_version() -> None:
    changelog = resources.CHANGELOG.read_text()

    # There is a changelog entry for the current version.
    version_line_pattern = re.compile(r"^## v([0-9\.]+) \([0-9-]+\) \{#v\1\}$", re.M)
    known_versions = [m[1] for m in version_line_pattern.finditer(changelog)]
    assert _GANZUA_VERSION in known_versions

    # There is a link to the full diff on GitHub.
    diff_link_pattern = re.compile(
        r"^Full diff: <https://github.com/latk/ganzua/compare/([^/\n]+)>$", re.M
    )
    known_diffs = [m[1] for m in diff_link_pattern.finditer(changelog)]
    prev_version = known_versions[known_versions.index(_GANZUA_VERSION) + 1]
    assert f"v{prev_version}...v{_GANZUA_VERSION}" in known_diffs


def _bump_mentioned_versions(readme: str) -> str:
    # Subset of the version specifier grammar, originally from PEP 508
    # https://packaging.python.org/en/latest/specifications/dependency-specifiers/#grammar
    version_cmp = r"\s* (?:<=|<|!=|===|==|>=|>|~=)"
    version = r"\s* [a-z0-9_.*+!-]+"
    version_one = rf"{version_cmp} {version} \s*"
    version_many = rf"{version_one} (?:, {version_one})*"  # deny trailing comma
    ganzua_constraint = re.compile(rf"\b ganzua \s* {version_many}", flags=re.X | re.I)

    edit = UpdateRequirement(
        {"packages": {"ganzua": {"version": _GANZUA_VERSION, "source": "other"}}}
    )

    return ganzua_constraint.sub(
        lambda m: apply_one_pep508_edit(
            m[0], edit, in_groups=frozenset(), in_extra=None
        ),
        readme,
    )
