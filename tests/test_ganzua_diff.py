from inline_snapshot import snapshot

from ganzua.cli import app

from . import resources

run = app.testrunner()


def test_json() -> None:
    old = resources.OLD_UV_LOCKFILE
    new = resources.NEW_UV_LOCKFILE
    output = run.json("diff", old, new)
    assert output == snapshot(
        {
            "packages": {
                "annotated-types": {
                    "old": None,
                    "new": {"version": "0.7.0", "source": "pypi"},
                },
                "typing-extensions": {
                    "old": {"version": "3.10.0.2", "source": "pypi"},
                    "new": {"version": "4.14.1", "source": "pypi"},
                    "is_major_change": True,
                },
            },
            "stat": {"total": 2, "added": 1, "removed": 0, "updated": 1},
        }
    )

    # can also pass directories
    assert run.json("diff", old, new.parent) == output
    assert run.json("diff", old.parent, new) == output
    assert run.json("diff", old.parent, new.parent) == output


def test_markdown() -> None:
    old = resources.OLD_UV_LOCKFILE
    new = resources.NEW_UV_LOCKFILE

    assert run.stdout("diff", "--format=markdown", old, new) == snapshot("""\
2 changed packages (1 added, 1 updated)

| package           | old      | new    | notes |
|-------------------|----------|--------|-------|
| annotated-types   | -        | 0.7.0  |       |
| typing-extensions | 3.10.0.2 | 4.14.1 | (M)   |

* (M) major change
""")

    # the same diff in reverse
    assert run.stdout("diff", "--format=markdown", new, old) == snapshot("""\
2 changed packages (1 updated, 1 removed)

| package           | old    | new      | notes   |
|-------------------|--------|----------|---------|
| annotated-types   | 0.7.0  | -        |         |
| typing-extensions | 4.14.1 | 3.10.0.2 | (M) (D) |

* (M) major change
* (D) downgrade
""")


def test_markdown_source_change() -> None:
    """Source changes are noted below the table.

    When multiple entries have the same note, the IDs are deduplicated.
    """
    old = resources.SOURCES_POETRY_LOCKFILE
    new = resources.SOURCES_UV_LOCKFILE

    assert run.stdout("diff", "--format=markdown", old, new) == snapshot("""\
6 changed packages (1 added, 5 updated)

| package            | old   | new   | notes |
|--------------------|-------|-------|-------|
| click              | 8.3.0 | 8.3.0 | (S1)  |
| click-example-repo | 1.0.0 | 1.0.0 | (S2)  |
| colorama           | 0.4.6 | 0.4.6 | (S1)  |
| idna               | 3.11  | 3.11  | (S1)  |
| propcache          | 0.4.1 | 0.4.1 | (S1)  |
| sources-uv         | -     | 0.1.0 |       |

* (S1) source changed from default to pypi
* (S2) source changed from <git+https://github.com/pallets/click.git@309ce9178707e1efaf994f191d062edbdffd5ce6#subdirectory=examples/repo> to <git+https://github.com/pallets/click.git@f67abc6fe7dd3d878879a4f004866bf5acefa9b4#subdirectory=examples/repo>
""")


def test_markdown_no_notes() -> None:
    """If there are no notes, the entire column is omitted."""
    old = resources.NEW_UV_LOCKFILE
    new = resources.MINOR_UV_LOCKFILE

    assert run.stdout("diff", "--format=markdown", old, new) == snapshot("""\
1 changed packages (1 updated)

| package           | old    | new    |
|-------------------|--------|--------|
| typing-extensions | 4.14.1 | 4.15.0 |
""")


def test_markdown_empty() -> None:
    lockfile = resources.NEW_UV_LOCKFILE
    assert run.stdout("diff", "--format=markdown", lockfile, lockfile) == snapshot(
        "0 changed packages\n"
    )
