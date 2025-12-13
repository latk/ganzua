import contextlib
import pathlib

from inline_snapshot import snapshot

from ganzua.cli import app

from . import resources
from .helpers import CLICK_ERROR, write_file

run = app.testrunner()


def test_json(tmp_path: pathlib.Path) -> None:
    lockfile = resources.OLD_UV_LOCKFILE
    output = run.json("inspect", lockfile)
    assert output == snapshot(
        {
            "packages": {
                "example": {
                    "version": "0.1.0",
                    "source": {"direct": "."},
                },
                "typing-extensions": {
                    "version": "3.10.0.2",
                    "source": "pypi",
                },
            }
        }
    )

    # can also use a directory
    assert run.json("inspect", lockfile.parent) == output

    # behavior when no explicit lockfile argument is passed
    with contextlib.chdir(tmp_path):
        # fails in empty directory
        result = run("inspect", expect_exit=CLICK_ERROR)
        assert "Could not infer `LOCKFILE` for `.`." in result.stderr

        # but finds the lockfile if present
        write_file(tmp_path / "uv.lock", source=lockfile)
        assert run.json("inspect") == output


def test_markdown() -> None:
    output = run.output("inspect", "--format=markdown", resources.OLD_UV_LOCKFILE)
    assert output == snapshot(
        """\
| package           | version  |
|-------------------|----------|
| example           | 0.1.0    |
| typing-extensions | 3.10.0.2 |
"""
    )
