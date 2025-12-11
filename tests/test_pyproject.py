import typing as t

from inline_snapshot import snapshot
from packaging.markers import Marker

import ganzua
import ganzua._toml as toml
from ganzua._lockfile import Lockfile
from ganzua._requirement import Name, Requirement, assert_normalized_name

_LOCKFILE: Lockfile = {
    "packages": {
        "annotated-types": {"version": "0.7.0", "source": "default"},
        "example": {"version": "0.2.0", "source": "default"},
        "typing-extensions": {"version": "4.14.1", "source": "default"},
    }
}

_OLD_PYPROJECT = """\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "Typing.Extensions>=3,<4",  # moar type annotations
    "merrily-ignored",
    [42, "also ignored"],  # we ignore invalid junk
]

[project.optional-dependencies]
extra1 = [
    "annotated-types >=0.6.1, ==0.6.*",
]
extra2 = false  # known invalid
extra3 = ["ndr"]

[dependency-groups]
group-a = ["typing-extensions ~=3.4"]
group-b = [{include-group = "group-a"}, "annotated-types ~=0.6.1"]
"""


_OLD_POETRY_PYPROJECT = """\
[tool.poetry.dependencies]
Typing_Extensions = "^3.2"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "^3.4" }
already-unconstrained = "*"
"""


def _apply_edit(edit: ganzua.EditRequirement, input: str) -> str:
    doc = toml.RefRoot.parse(input)
    ganzua.edit_pyproject(doc, edit)
    return doc.dumps()


def test_update_pep621() -> None:
    edit = ganzua.UpdateRequirement(_LOCKFILE)
    assert _apply_edit(edit, _OLD_PYPROJECT) == snapshot(
        """\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "Typing.Extensions>=4,<5",  # moar type annotations
    "merrily-ignored",
    [42, "also ignored"],  # we ignore invalid junk
]

[project.optional-dependencies]
extra1 = [
    "annotated-types>=0.7.0,==0.7.*",
]
extra2 = false  # known invalid
extra3 = ["ndr"]

[dependency-groups]
group-a = ["typing-extensions~=4.14"]
group-b = [{include-group = "group-a"}, "annotated-types~=0.7.0"]
"""
    )


def test_update_poetry() -> None:
    edit = ganzua.UpdateRequirement(_LOCKFILE)
    assert _apply_edit(edit, _OLD_POETRY_PYPROJECT) == snapshot(
        """\
[tool.poetry.dependencies]
Typing_Extensions = "^4.14"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "^4.14" }
already-unconstrained = "*"
"""
    )


def test_update_empty() -> None:
    edit = ganzua.UpdateRequirement(_LOCKFILE)
    assert _apply_edit(edit, "") == ""


def test_unconstrain_pep621() -> None:
    edit = ganzua.UnconstrainRequirement()
    assert _apply_edit(edit, _OLD_PYPROJECT) == snapshot(
        """\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "Typing.Extensions",  # moar type annotations
    "merrily-ignored",
    [42, "also ignored"],  # we ignore invalid junk
]

[project.optional-dependencies]
extra1 = [
    "annotated-types",
]
extra2 = false  # known invalid
extra3 = ["ndr"]

[dependency-groups]
group-a = ["typing-extensions"]
group-b = [{include-group = "group-a"}, "annotated-types"]
"""
    )


def test_unconstrain_poetry() -> None:
    edit = ganzua.UnconstrainRequirement()
    assert _apply_edit(edit, _OLD_POETRY_PYPROJECT) == snapshot(
        """\
[tool.poetry.dependencies]
Typing_Extensions = "*"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "*" }
already-unconstrained = "*"
"""
    )


def test_set_minimum_pep621() -> None:
    edit = ganzua.SetMinimumRequirement(_LOCKFILE)
    assert _apply_edit(edit, _OLD_PYPROJECT) == snapshot(
        """\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "Typing.Extensions>=4.14.1",  # moar type annotations
    "merrily-ignored",
    [42, "also ignored"],  # we ignore invalid junk
]

[project.optional-dependencies]
extra1 = [
    "annotated-types>=0.7.0",
]
extra2 = false  # known invalid
extra3 = ["ndr"]

[dependency-groups]
group-a = ["typing-extensions>=4.14.1"]
group-b = [{include-group = "group-a"}, "annotated-types>=0.7.0"]
"""
    )


def _collect_requirements(pyproject_contents: str) -> list[Requirement]:
    collector = ganzua.CollectRequirement([])
    _apply_edit(collector, pyproject_contents)
    return collector.reqs


def test_list_pep621() -> None:
    assert _collect_requirements(_OLD_PYPROJECT) == snapshot(
        [
            Requirement(
                name=assert_normalized_name("typing-extensions"), specifier="<4,>=3"
            ),
            Requirement(name=assert_normalized_name("merrily-ignored"), specifier=""),
            Requirement(
                name=assert_normalized_name("annotated-types"),
                specifier="==0.6.*,>=0.6.1",
                in_extras=_nameset("extra1"),
            ),
            Requirement(
                name=assert_normalized_name("ndr"),
                specifier="",
                in_extras=_nameset("extra3"),
            ),
            Requirement(
                name=assert_normalized_name("typing-extensions"),
                specifier="~=3.4",
                groups=_nameset("group-a", "group-b"),
            ),
            Requirement(
                name=assert_normalized_name("annotated-types"),
                specifier="~=0.6.1",
                groups=_nameset("group-b"),
            ),
        ]
    )


def test_list_empty() -> None:
    assert _collect_requirements("") == []


def test_list_poetry() -> None:
    assert _collect_requirements(_OLD_POETRY_PYPROJECT) == snapshot(
        [
            Requirement(
                name=assert_normalized_name("typing-extensions"), specifier="^3.2"
            ),
            Requirement(
                name=assert_normalized_name("typing-extensions"),
                specifier="^3.4",
                groups=_nameset("poetry-a"),
            ),
            Requirement(
                name=assert_normalized_name("already-unconstrained"),
                specifier="*",
                groups=_nameset("poetry-a"),
            ),
        ]
    )


def test_list_groups() -> None:
    pyproject = """\
[dependency-groups]
a = [{include-group = "c"}]
D = ["other"]
b = ["example-pep735 >=3"]
c = [{include-group = "B"}]

[tool.poetry.group.PA.dependencies]
example-poetry = "^3"
[tool.poetry.group.pb.dependencies]
example-poetry = ">=3"
"""

    assert _collect_requirements(pyproject) == snapshot(
        [
            Requirement(
                name=assert_normalized_name("other"), specifier="", groups=_nameset("d")
            ),
            Requirement(
                name=assert_normalized_name("example-pep735"),
                specifier=">=3",
                groups=_nameset("a", "b", "c"),
            ),
            Requirement(
                name=assert_normalized_name("example-poetry"),
                specifier="^3",
                groups=_nameset("pa"),
            ),
            Requirement(
                name=assert_normalized_name("example-poetry"),
                specifier=">=3",
                groups=_nameset("pb"),
            ),
        ]
    )


def test_list_extras() -> None:
    pyproject = """\
[project.optional-dependencies]
a = ["foo[xtra,XtRb] ~=3.0"]

[tool.poetry.dependencies]
bar = { version = "^3", optional = true, extras = ["xtra", "xTrB"] }

[tool.poetry.extras]
b = ["bar"]
c = ["bar", "ignored"]
"""

    assert _collect_requirements(pyproject) == snapshot(
        [
            Requirement(
                name=assert_normalized_name("foo"),
                specifier="~=3.0",
                extras=_nameset("xtra", "xtrb"),
                in_extras=_nameset("a"),
            ),
            Requirement(
                name=assert_normalized_name("bar"),
                specifier="^3",
                extras=_nameset("xtra", "xtrb"),
                in_extras=_nameset("b", "c"),
            ),
        ]
    )


def test_list_markers() -> None:
    pyproject = """\
[project]
dependencies = ["foo >= 3 ; python_version <= '3.11'"]

[tool.poetry.dependencies]
bar = { version = "^3", markers = "python_version <= '3.11'" }
"""

    assert _collect_requirements(pyproject) == snapshot(
        [
            Requirement(
                name=assert_normalized_name("foo"),
                specifier=">=3",
                marker=Marker("python_version <= '3.11'"),
            ),
            Requirement(
                name=assert_normalized_name("bar"),
                specifier="^3",
                marker=Marker("python_version <= '3.11'"),
            ),
        ]
    )


def _nameset(*names: t.LiteralString) -> frozenset[Name]:
    return frozenset(assert_normalized_name(name) for name in names)
