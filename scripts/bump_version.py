#!/usr/bin/env python3

import datetime as dt
import difflib
import itertools
import pathlib
import re
import shlex
import subprocess
import typing as t

import click
import rich.panel
import rich.syntax


@click.command
@click.option("--apply/--dry-run", required=True)
@click.argument("version")
def main(version: str, apply: bool) -> None:
    """Update the Ganzua version, and fix up references in the docs/changelogs."""
    # Set the project version
    _check_call(["uv", "version", version], apply=apply)

    for path in _files_that_may_contain_original_docs():
        _update_ganzua_next_version_in_file(path, version, apply=apply)

    _update_changelog_contents(
        pathlib.Path("CHANGELOG.md"), version, dt.date.today(), apply=apply
    )

    click.echo("Remember to re-run all tests if there were *any* changes.")


def _files_that_may_contain_original_docs() -> t.Iterator[pathlib.Path]:
    yield pathlib.Path("README.md")
    yield from pathlib.Path("docs/").glob("**/*.md")
    yield from pathlib.Path("src/").glob("**/*.py")


def _update_ganzua_next_version_in_file(
    path: pathlib.Path, version: str, *, apply: bool
) -> None:
    """Replace all occurrences of `Ganzua NEXT` with the given version in the file."""
    old = path.read_text()
    new = re.sub(r"(\b[Gg]anzua )NEXT\b", r"\g<1>" + version, old)
    if old != new:
        _print_diff(old, new, title=f"{path}: set NEXT version")
        if apply:
            path.write_text(new)


def _update_changelog_contents(
    path: pathlib.Path, version: str, date: dt.date, *, apply: bool
) -> None:
    """Replace the `Unreleased` header in the changelog."""
    old = path.read_text()
    new = "\n".join(_transscribe_changelog_lines(old.splitlines(), version, date))
    if old != new:
        _print_diff(old, new, title=f"{path}: updated changelog")
        if apply:
            path.write_text(new)


def _transscribe_changelog_lines(
    old_lines: t.Iterable[str], version: str, date: dt.date
) -> t.Iterator[str]:
    in_comment = False
    for line in old_lines:
        if in_comment:
            yield line
            if "-->" in line:
                in_comment = False
            continue

        if line.startswith("<!--") and "-->" not in line:
            yield line
            in_comment = True
            continue

        if line == "## Unreleased":
            yield f"## v{version} ({date}) {{#v{version}}}"
            continue

        yield re.sub(
            r"<(https://github\.com/[^/>]++/[^/>]++/compare/[^>]+)\.\.\.HEAD>",
            r"<\g<1>..." + version + ">",
            line,
        )


def _check_call(cmd: list[str], *, apply: bool) -> None:
    click.echo(f"running: `{shlex.join(cmd)}`")
    if apply:
        subprocess.check_call(cmd)


def _print_diff(old: str, new: str, *, title: str) -> None:
    lazy_diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="")
    lazy_diff = itertools.islice(lazy_diff, 2, None)  # skip the `---` and `+++` lines
    highlighted_diff = rich.syntax.Syntax("\n".join(lazy_diff), "diff", word_wrap=True)
    rich.print(rich.panel.Panel(highlighted_diff, title=title))


if __name__ == "__main__":
    main()
