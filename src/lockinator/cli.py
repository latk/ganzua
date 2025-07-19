"""The lockinator command-line interface."""

import pathlib

import rich
import typer

import lockinator

app = typer.Typer()


@app.command()
def inspect(lockfile: pathlib.Path) -> None:
    """Inspect a lockfile."""
    rich.print_json(data=lockinator.lockfile_from(lockfile))


@app.command()
def diff(old: pathlib.Path, new: pathlib.Path) -> None:
    """Compare two lockfiles."""
    rich.print_json(
        data=lockinator.diff(
            lockinator.lockfile_from(old), lockinator.lockfile_from(new)
        )
    )
