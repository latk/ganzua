#!/usr/bin/env python
# ruff: noqa: S607  # start-process-with-partial-path

"""Dirty script to keep the usage section in the README up to date."""

import pathlib
import re
import subprocess
import sys
import tempfile

import click

README = pathlib.Path("./README.md")

BEGIN = "\n<!-- begin usage -->\n"
END = "\n<!-- end usage -->\n"
PATTERN = re.compile(re.escape(BEGIN) + "(.*)" + END, re.S)


@click.group()
def app() -> None:
    """Dirty script to keep the usage section in the README up to date."""


@app.command()
def extract_command() -> None:
    """Get the current usage section in the README."""
    click.echo(_usage_from_readme())


@app.command()
def diff_command() -> None:
    """Show a diff between the usage in the README and in the CLI help."""
    with tempfile.TemporaryDirectory() as tempdir:
        usage_from_readme = pathlib.Path(tempdir) / "readme.md"
        usage_from_readme.write_text(_usage_from_readme())
        usage_from_cli = pathlib.Path(tempdir) / "cli.md"
        usage_from_cli.write_text(_usage_from_cli())
        try:
            subprocess.check_call(
                ["git", "diff", "--no-index", usage_from_readme, usage_from_cli]
            )
        except subprocess.CalledProcessError:
            sys.exit(1)


@app.command()
def update_command() -> None:
    """Update the README to match the usage from the CLI."""
    usage = _usage_from_cli()
    old = README.read_text()
    new = PATTERN.sub(f"{BEGIN}\n{usage}\n{END}", old)
    README.write_text(new)


def _usage_from_readme() -> str:
    if m := PATTERN.search(README.read_text()):
        return m.group(1).strip()
    return ""


def _usage_from_cli() -> str:
    return subprocess.check_output(
        ["ganzua", "help", "--all", "--markdown"], encoding="utf-8"
    ).strip()


if __name__ == "__main__":
    app()
