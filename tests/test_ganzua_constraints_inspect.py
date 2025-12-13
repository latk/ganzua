import contextlib
import pathlib

from inline_snapshot import snapshot

from ganzua.cli import app

from . import resources
from .helpers import CLICK_ERROR, write_file

run = app.testrunner()


def test_inspect() -> None:
    assert run.json("constraints", "inspect", resources.NEW_UV_PYPROJECT) == snapshot(
        {
            "requirements": [
                {"name": "annotated-types", "specifier": ">=0.7.0"},
                {"name": "typing-extensions", "specifier": ">=4"},
            ]
        }
    )


def test_groups_and_extras() -> None:
    assert run.json(
        "constraints", "inspect", resources.POETRY_MULTIPLE_GROUPS_PYPROJECT
    ) == snapshot(
        {
            "requirements": [
                {"name": "annotated-types", "specifier": ">=0.7.0"},
                {
                    "name": "annotated-types",
                    "specifier": "<0.8.0",
                    "in_groups": ["dev", "types"],
                },
                {
                    "name": "typing-extensions",
                    "specifier": "<5.0.0,>=4.15.0",
                    "in_groups": ["types"],
                },
                {
                    "name": "typing-extensions",
                    "specifier": "^4.15",
                    "in_extras": ["dev", "types"],
                },
            ]
        }
    )


def test_markdown() -> None:
    assert run.stdout(
        "constraints", "inspect", "--format=markdown", resources.NEW_UV_PYPROJECT
    ) == snapshot("""\
| package           | version |
|-------------------|---------|
| annotated-types   | >=0.7.0 |
| typing-extensions | >=4     |
""")


def test_markdown_groups_and_extras() -> None:
    assert run.stdout(
        "constraints",
        "inspect",
        "--format=markdown",
        resources.POETRY_MULTIPLE_GROUPS_PYPROJECT,
    ) == snapshot("""\
| package           | version         | group/extra                |
|-------------------|-----------------|----------------------------|
| annotated-types   | <0.8.0          | group `dev`, group `types` |
| annotated-types   | >=0.7.0         |                            |
| typing-extensions | <5.0.0,>=4.15.0 | group `types`              |
| typing-extensions | ^4.15           | extra `dev`, extra `types` |
""")


def test_has_default_pyproject(tmp_path: pathlib.Path) -> None:
    cmd = run.bind("constraints", "inspect")
    with contextlib.chdir(tmp_path):
        # running in an empty tempdir fails
        result = cmd(expect_exit=CLICK_ERROR)
        assert "Did not find default `pyproject.toml`." in result.output

        # but a `pyproject.toml` in the CWD is picked up automatically
        pyproject = write_file("pyproject.toml", source=resources.NEW_UV_PYPROJECT)
        expected_output = cmd.output(pyproject)
        assert cmd.output() == expected_output

    # it's also possible to specify just the directory
    assert cmd.output(tmp_path) == expected_output
