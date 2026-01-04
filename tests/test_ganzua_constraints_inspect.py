import contextlib
import pathlib

from inline_snapshot import snapshot

from ganzua.cli import app

from . import resources
from .helpers import CLICK_ERROR, write_file

inspect = app.testrunner().bind("constraints", "inspect")


def test_has_default_pyproject(tmp_path: pathlib.Path) -> None:
    with contextlib.chdir(tmp_path):
        # running in an empty tempdir fails
        result = inspect(expect_exit=CLICK_ERROR)
        assert "Did not find default `pyproject.toml`." in result.output

        # but a `pyproject.toml` in the CWD is picked up automatically
        pyproject = write_file("pyproject.toml", source=resources.NEW_UV_PYPROJECT)
        expected_output = inspect.output(pyproject)
        assert inspect.output() == expected_output

    # it's also possible to specify just the directory
    assert inspect.output(tmp_path) == expected_output


def test_pep621(tmp_path: pathlib.Path) -> None:
    pyproject = write_file(
        tmp_path / "pyproject.toml", data=resources.CONSTRAINTS_PYPROJECT_CONTENTS
    )
    assert inspect.json(pyproject) == snapshot(
        {
            "requirements": [
                {"name": "typing-extensions", "specifier": "<4,>=3"},
                {"name": "merrily-ignored", "specifier": ""},
                {
                    "name": "annotated-types",
                    "specifier": "==0.6.*,>=0.6.1",
                    "in_extras": ["extra1"],
                },
                {"name": "ndr", "specifier": "", "in_extras": ["extra3"]},
                {
                    "name": "typing-extensions",
                    "specifier": "~=3.4",
                    "in_groups": ["group-a", "group-b"],
                },
                {
                    "name": "annotated-types",
                    "specifier": "~=0.6.1",
                    "in_groups": ["group-b"],
                },
            ]
        }
    )


def test_empty(tmp_path: pathlib.Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("")
    assert inspect.json(pyproject) == {"requirements": []}


def test_poetry(tmp_path: pathlib.Path) -> None:
    pyproject = write_file(
        tmp_path / "pyproject.toml",
        data=resources.CONSTRAINTS_POETRY_PYPROJECT_CONTENTS,
    )
    assert inspect.json(pyproject) == snapshot(
        {
            "requirements": [
                {"name": "typing-extensions", "specifier": "^3.2"},
                {
                    "name": "typing-extensions",
                    "specifier": "^3.4",
                    "in_groups": ["poetry-a"],
                },
                {
                    "name": "already-unconstrained",
                    "specifier": "*",
                    "in_groups": ["poetry-a"],
                },
            ]
        }
    )


def test_groups(tmp_path: pathlib.Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""\
[dependency-groups]
a = [{include-group = "c"}]
D = ["other"]
b = ["example-pep735 >=3"]
c = [{include-group = "B"}]

[tool.poetry.group.PA.dependencies]
example-poetry = "^3"
[tool.poetry.group.pb.dependencies]
example-poetry = ">=3"
""")

    assert inspect.json(pyproject) == snapshot(
        {
            "requirements": [
                {"name": "other", "specifier": "", "in_groups": ["d"]},
                {
                    "name": "example-pep735",
                    "specifier": ">=3",
                    "in_groups": ["a", "b", "c"],
                },
                {"name": "example-poetry", "specifier": "^3", "in_groups": ["pa"]},
                {"name": "example-poetry", "specifier": ">=3", "in_groups": ["pb"]},
            ]
        }
    )


def test_extras(tmp_path: pathlib.Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""\
[project.optional-dependencies]
a = ["foo[xtra,XtRb] ~=3.0"]

[tool.poetry.dependencies]
bar = { version = "^3", optional = true, extras = ["xtra", "xTrB"] }

[tool.poetry.extras]
b = ["bar"]
c = ["bar", "ignored"]
""")

    assert inspect.json(pyproject) == snapshot(
        {
            "requirements": [
                {
                    "name": "foo",
                    "specifier": "~=3.0",
                    "extras": ["xtra", "xtrb"],
                    "in_extras": ["a"],
                },
                {
                    "name": "bar",
                    "specifier": "^3",
                    "extras": ["xtra", "xtrb"],
                    "in_extras": ["b", "c"],
                },
            ]
        }
    )


def test_markers(tmp_path: pathlib.Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""\
[project]
dependencies = ["foo >= 3 ; python_version <= '3.11'"]

[tool.poetry.dependencies]
bar = { version = "^3", markers = "python_version <= '3.11'" }
""")

    assert inspect.json(pyproject) == snapshot(
        {
            "requirements": [
                {
                    "name": "foo",
                    "specifier": ">=3",
                    "marker": 'python_version <= "3.11"',
                },
                {
                    "name": "bar",
                    "specifier": "^3",
                    "marker": 'python_version <= "3.11"',
                },
            ]
        }
    )
