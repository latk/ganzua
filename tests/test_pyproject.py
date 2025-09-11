import tomlkit
from inline_snapshot import snapshot
from packaging.markers import Marker

import ganzua
from ganzua._constraints import Requirement
from ganzua._lockfile import Lockfile

_LOCKFILE: Lockfile = {
    "packages": {
        "annotated-types": {"version": "0.7.0"},
        "example": {"version": "0.2.0"},
        "typing-extensions": {"version": "4.14.1"},
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
    "typing-extensions>=3,<4",  # moar type annotations
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

_EXPECTED_PYPROJECT = """\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "typing-extensions>=4,<5",  # moar type annotations
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

_UNCONSTRAINED_PYPROJECT = """\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "typing-extensions",  # moar type annotations
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

_OLD_POETRY_PYPROJECT = """\
[tool.poetry.dependencies]
typing-extensions = "^3.2"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "^3.4" }
already-unconstrained = "*"
"""

_EXPECTED_POETRY_PYPROJECT = """\
[tool.poetry.dependencies]
typing-extensions = "^4.14"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "^4.14" }
already-unconstrained = "*"
"""

_UNCONSTRAINED_POETRY_PYPROJECT = """\
[tool.poetry.dependencies]
typing-extensions = "*"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "*" }
already-unconstrained = "*"
"""


def test_update_pep621() -> None:
    doc = tomlkit.parse(_OLD_PYPROJECT)
    ganzua.edit_pyproject(doc, ganzua.UpdateRequirement(_LOCKFILE))
    assert doc.as_string() == _EXPECTED_PYPROJECT


def test_update_poetry() -> None:
    doc = tomlkit.parse(_OLD_POETRY_PYPROJECT)
    ganzua.edit_pyproject(doc, ganzua.UpdateRequirement(_LOCKFILE))
    assert doc.as_string() == _EXPECTED_POETRY_PYPROJECT


def test_update_empty() -> None:
    doc = tomlkit.document()
    ganzua.edit_pyproject(doc, ganzua.UpdateRequirement(_LOCKFILE))
    assert doc.as_string() == ""


def test_unconstrain_pep621() -> None:
    doc = tomlkit.parse(_OLD_PYPROJECT)
    ganzua.edit_pyproject(doc, ganzua.UnconstrainRequirement())
    assert doc.as_string() == _UNCONSTRAINED_PYPROJECT


def test_unconstrain_poetry() -> None:
    doc = tomlkit.parse(_OLD_POETRY_PYPROJECT)
    ganzua.edit_pyproject(doc, ganzua.UnconstrainRequirement())
    assert doc.as_string() == _UNCONSTRAINED_POETRY_PYPROJECT


def test_set_minimum_pep621() -> None:
    doc = tomlkit.parse(_OLD_PYPROJECT)
    ganzua.edit_pyproject(doc, ganzua.SetMinimumRequirement(_LOCKFILE))
    assert doc.as_string() == snapshot("""\
[project]
name = "example"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "typing-extensions>=4.14.1",  # moar type annotations
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
""")


def _collect_requirements(pyproject_contents: str) -> list[Requirement]:
    doc = tomlkit.parse(pyproject_contents)
    collector = ganzua.CollectRequirement([])
    ganzua.edit_pyproject(doc, collector)
    return collector.reqs


def test_list_pep621() -> None:
    assert _collect_requirements(_OLD_PYPROJECT) == snapshot(
        [
            Requirement(name="typing-extensions", specifier="<4,>=3"),
            Requirement(name="merrily-ignored", specifier=""),
            Requirement(name="annotated-types", specifier="==0.6.*,>=0.6.1"),
            Requirement(name="ndr", specifier=""),
            Requirement(
                name="typing-extensions",
                specifier="~=3.4",
                groups=frozenset(("group-a", "group-b")),
            ),
            Requirement(
                name="annotated-types",
                specifier="~=0.6.1",
                groups=frozenset(("group-b",)),
            ),
        ]
    )


def test_list_empty() -> None:
    assert _collect_requirements("") == []


def test_list_poetry() -> None:
    assert _collect_requirements(_OLD_POETRY_PYPROJECT) == snapshot(
        [
            Requirement(name="typing-extensions", specifier="^3.2"),
            Requirement(
                name="typing-extensions",
                specifier="^3.4",
                groups=frozenset(("poetry-a",)),
            ),
            Requirement(
                name="already-unconstrained",
                specifier="*",
                groups=frozenset(("poetry-a",)),
            ),
        ]
    )


def test_list_groups() -> None:
    pyproject = """\
[dependency-groups]
a = [{include-group = "c"}]
d = ["other"]
b = ["example-pep735 >=3"]
c = [{include-group = "b"}]

[tool.poetry.group.pa.dependencies]
example-poetry = "^3"
[tool.poetry.group.pb.dependencies]
example-poetry = ">=3"
"""

    assert _collect_requirements(pyproject) == snapshot(
        [
            Requirement(name="other", specifier="", groups=frozenset(("d",))),
            Requirement(
                name="example-pep735",
                specifier=">=3",
                groups=frozenset(("a", "b", "c")),
            ),
            Requirement(
                name="example-poetry", specifier="^3", groups=frozenset(("pa",))
            ),
            Requirement(
                name="example-poetry", specifier=">=3", groups=frozenset(("pb",))
            ),
        ]
    )


def test_list_extras() -> None:
    pyproject = """\
[project.optional-dependencies]
a = ["foo[xtra,xtrb] ~=3.0"]

[tool.poetry.dependencies]
bar = { version = "^3", optional = true, extras = ["xtra", "xtrb"] }

[tool.poetry.extras]
b = ["bar"]
"""

    assert _collect_requirements(pyproject) == snapshot(
        [
            Requirement(
                name="foo", specifier="~=3.0", extras=frozenset(("xtra", "xtrb"))
            ),
            Requirement(name="bar", specifier="^3", extras=frozenset(("xtra", "xtrb"))),
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
                name="foo", specifier=">=3", marker=Marker("python_version <= '3.11'")
            ),
            Requirement(
                name="bar", specifier="^3", marker=Marker("python_version <= '3.11'")
            ),
        ]
    )
