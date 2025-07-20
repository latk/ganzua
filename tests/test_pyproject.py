import tomlkit

import lockinator
from lockinator._lockfile import Lockfile

_LOCKFILE: Lockfile = {
    "annotated-types": {"version": "0.7.0"},
    "example": {"version": "0.2.0"},
    "typing-extensions": {"version": "4.14.1"},
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

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "^3.4" }
already-unconstrained = "*"
"""

_EXPECTED_POETRY_PYPROJECT = """\
[tool.poetry.dependencies]
typing-extensions = "^4.14"
ignored-garbage = { not-a-version = true }

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "^4.14" }
already-unconstrained = "*"
"""

_UNCONSTRAINED_POETRY_PYPROJECT = """\
[tool.poetry.dependencies]
typing-extensions = "*"
ignored-garbage = { not-a-version = true }

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "*" }
already-unconstrained = "*"
"""


def test_update_pep621() -> None:
    doc = tomlkit.parse(_OLD_PYPROJECT)
    lockinator.update_pyproject(doc, _LOCKFILE)
    assert doc.as_string() == _EXPECTED_PYPROJECT


def test_update_poetry() -> None:
    doc = tomlkit.parse(_OLD_POETRY_PYPROJECT)
    lockinator.update_pyproject(doc, _LOCKFILE)
    assert doc.as_string() == _EXPECTED_POETRY_PYPROJECT


def test_update_empty() -> None:
    doc = tomlkit.document()
    lockinator.update_pyproject(doc, _LOCKFILE)
    assert doc.as_string() == ""


def test_unconstrain_pep621() -> None:
    doc = tomlkit.parse(_OLD_PYPROJECT)
    lockinator.unconstrain_pyproject(doc)
    assert doc.as_string() == _UNCONSTRAINED_PYPROJECT


def test_unconstrain_poetry() -> None:
    doc = tomlkit.parse(_OLD_POETRY_PYPROJECT)
    lockinator.unconstrain_pyproject(doc)
    assert doc.as_string() == _UNCONSTRAINED_POETRY_PYPROJECT
