import contextlib
import pathlib

from inline_snapshot import snapshot

from ganzua.cli import app

from . import resources
from .helpers import CLICK_ERROR, write_file

inspect = app.testrunner().bind("constraints", "inspect")


def test_inspect() -> None:
    assert inspect.json(resources.NEW_UV_PYPROJECT) == snapshot(
        {
            "requirements": [
                {"name": "annotated-types", "specifier": ">=0.7.0"},
                {"name": "typing-extensions", "specifier": ">=4"},
            ]
        }
    )


def test_groups_and_extras() -> None:
    assert inspect.json(resources.POETRY_MULTIPLE_GROUPS_PYPROJECT) == snapshot(
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
    assert inspect.stdout("--format=markdown", resources.NEW_UV_PYPROJECT) == snapshot("""\
| package           | version |
|-------------------|---------|
| annotated-types   | >=0.7.0 |
| typing-extensions | >=4     |
""")


def test_markdown_groups_and_extras() -> None:
    assert inspect.stdout(
        "--format=markdown", resources.POETRY_MULTIPLE_GROUPS_PYPROJECT
    ) == snapshot("""\
| package           | version         | group/extra                |
|-------------------|-----------------|----------------------------|
| annotated-types   | <0.8.0          | group `dev`, group `types` |
| annotated-types   | >=0.7.0         |                            |
| typing-extensions | <5.0.0,>=4.15.0 | group `types`              |
| typing-extensions | ^4.15           | extra `dev`, extra `types` |
""")


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
