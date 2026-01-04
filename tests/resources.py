import importlib.resources
import pathlib

ROOT = importlib.resources.files() / ".."

# The `importlib.resources` API only guarantees the `Traversable` interface.
# This matters when resources aren't installed as actual files,
# e.g. when a Python package is installed as a Zip archive.
# However, these resources are only used during development,
# which always uses an editable install.
# So we know that these resources are ordinary file paths.
assert isinstance(ROOT, pathlib.Path)  # noqa: S101  # assert

CORPUS = ROOT / "corpus"
OLD_UV_LOCKFILE = CORPUS / "old-uv-project/uv.lock"
NEW_UV_LOCKFILE = CORPUS / "new-uv-project/uv.lock"
MINOR_UV_LOCKFILE = CORPUS / "minor-uv-project/uv.lock"
OLD_UV_PYPROJECT = CORPUS / "old-uv-project/pyproject.toml"
NEW_UV_PYPROJECT = CORPUS / "new-uv-project/pyproject.toml"
OLD_POETRY_LOCKFILE = CORPUS / "old-poetry-project/poetry.lock"
NEW_POETRY_LOCKFILE = CORPUS / "new-poetry-project/poetry.lock"
NEW_POETRY_PYPROJECT = CORPUS / "new-poetry-project/pyproject.toml"
SOURCES_POETRY_LOCKFILE = CORPUS / "sources-poetry/poetry.lock"
SOURCES_UV_LOCKFILE = CORPUS / "sources-uv/uv.lock"
SETUPTOOLS_DYNAMIC_VERSION_LOCKFILE = CORPUS / "setuptools-dynamic-version/uv.lock"
POETRY_MULTIPLE_GROUPS_PYPROJECT = CORPUS / "poetry-multiple-groups/pyproject.toml"

README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
DOCS = ROOT / "docs"
EMPTY = pathlib.Path("/dev/null")

CONSTRAINTS_PYPROJECT_CONTENTS = """\
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
"""Example for testing constraint operations."""

CONSTRAINTS_POETRY_PYPROJECT_CONTENTS = """\
[tool.poetry.dependencies]
Typing_Extensions = "^3.2"
ignored-garbage = { not-a-version = true }

[build-system]

[tool.poetry.group.poetry-a.dependencies]
typing-extensions = { version = "^3.4" }
already-unconstrained = "*"
"""
"""Example for testing constrain operations with some Poetry-specific features."""
