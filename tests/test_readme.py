import importlib.metadata
import re
import subprocess

import pytest
from inline_snapshot import external_file, snapshot

from ganzua import UpdateRequirement
from ganzua._pyproject import apply_one_pep508_edit
from ganzua.cli import app

from . import resources

run = app.testrunner()


def test_readme() -> None:
    """Test to ensure that the README is up to date.

    * matches current `ganzua help`
    * all doctests produce expected output
    """
    readme = resources.README.read_text()
    readme = _update_usage_section(readme)
    readme = _bump_mentioned_versions(readme)
    readme, executed_examples = _update_bash_doctests(readme)
    assert readme == external_file(str(resources.README), format=".txt")
    assert executed_examples == snapshot(3)


def _update_usage_section(readme: str) -> str:
    begin = "\n<!-- begin usage -->\n"
    end = "\n<!-- end usage -->\n"
    pattern = re.compile(re.escape(begin) + "(.*)" + re.escape(end), flags=re.S)
    up_to_date_usage = run.output("help", "--all", "--markdown").strip()
    return pattern.sub(f"{begin}\n{up_to_date_usage}\n{end}", readme)


def _bump_mentioned_versions(readme: str) -> str:
    # Subset of the version specifier grammar, originally from PEP 508
    # https://packaging.python.org/en/latest/specifications/dependency-specifiers/#grammar
    version_cmp = r"\s* (?:<=|<|!=|===|==|>=|>|~=)"
    version = r"\s* [a-z0-9_.*+!-]+"
    version_one = rf"{version_cmp} {version} \s*"
    version_many = rf"{version_one} (?:, {version_one})*"  # deny trailing comma
    ganzua_constraint = re.compile(rf"\b ganzua \s* {version_many}", flags=re.X | re.I)

    current_ganzua_version = importlib.metadata.version("ganzua")
    edit = UpdateRequirement(
        {"packages": {"ganzua": {"version": current_ganzua_version, "source": "other"}}}
    )

    return ganzua_constraint.sub(
        lambda m: apply_one_pep508_edit(
            m[0], edit, in_groups=frozenset(), in_extra=None
        ),
        readme,
    )


def _update_bash_doctests(readme: str) -> tuple[str, int]:
    fenced_example_pattern = re.compile(
        r"""
# start a fenced code block with `console` as the info string
^ (?P<delim> [`]{3,}+) [ ]*+ console [ ]*+ \n

# the next line must look like `$ command arg arg`
[$] (?P<command> [^\n]++) \n

# gobble up remaining contents of the fenced section as the output
(?P<output> .*?) \n

# match closing fence
(?P=delim) $
""",
        flags=re.MULTILINE | re.VERBOSE | re.DOTALL,
    )

    executed_examples = 0

    def run_example(m: re.Match) -> str:
        nonlocal executed_examples

        delim = m["delim"]
        command = m["command"].strip()
        assert command.startswith("ganzua ")
        output = _run_shell_command(command).rstrip()
        executed_examples += 1
        return f"{delim}console\n$ {command}\n{output}\n{delim}"

    updated_readme = fenced_example_pattern.sub(run_example, readme)
    return updated_readme, executed_examples


def _run_shell_command(command: str) -> str:
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setenv("TERM", "dumb")  # disable colors

        result = subprocess.run(
            # allow `bash` to be resolved via PATH
            ["bash", "-eu", "-o", "braceexpand", "-c", command],  # noqa: S607
            encoding="utf-8",
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    if result.returncode != 0:  # pragma: no cover
        pytest.fail(
            f"""\
Doctest shell command failed
command: {command}
exit code: {result.returncode}
--- captured stdout
{result.stdout}
--- captured stderr
{result.stderr}
--- end
"""
        )

    return result.stdout
