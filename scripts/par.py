#!/usr/bin/env python3

"""Run multiple commands in parallel.

Compare 'GNU Parallel' or 'pexec'.
This `par` helper does not buffer the output of spawned commands,
they will all be printed out interspersed.
"""

import asyncio
import collections
import shlex
import sys
from dataclasses import dataclass
from typing import Never, Sequence

BOLD = "\033[1m"
NORMAL = "\033[0m"
MAX_FAILED_TASKS_EXIT_STATUS = 16
USAGE: str = "[OPTIONS] TEMPLATE... ::: PARAMS..."


async def main() -> None:
    """Main entrypoint to run multiple commands in parallel."""
    args = _parse_cli_arguments(sys.argv[1:], name=sys.argv[0])

    results = await _run_all_tasks(args)
    num_errors = sum(1 for p in results.values() if p.returncode != 0)
    if num_errors == 0:
        return

    _warn(f"{BOLD}ERROR: {num_errors}/{len(results)} tasks failed{NORMAL}")
    for param, task in results.items():
        if task.returncode != 0:
            _warn(
                f"FAILED: param={shlex.quote(param)} pid={task.pid} exitcode={task.returncode}"
            )
    sys.exit(min(num_errors, MAX_FAILED_TASKS_EXIT_STATUS))


@dataclass(kw_only=True)
class _CliOptions:
    shell: bool = False


@dataclass
class _CliArguments(_CliOptions):
    template: Sequence[str]
    params: Sequence[str]


def _warn(msg: str, /) -> None:
    print(msg, file=sys.stderr)


def _die(msg: str, /, *, status: int = 17) -> Never:
    _warn(msg)
    sys.exit(status)


def _parse_cli_arguments(_args: Sequence[str], /, *, name: str) -> _CliArguments:
    args = collections.deque(_args)

    opts = _consume_options(args, name=name)
    template = _consume_template(args, opts=opts)

    # remaining args are params
    if not args:
        _die("ERROR: params cannot be empty")

    return _CliArguments(
        template=tuple(template),
        params=tuple(args),
        shell=opts.shell,
    )


def _consume_options(args: collections.deque[str], *, name: str) -> _CliOptions:
    if not args:
        _die(f"USAGE: {name} {USAGE}")

    opts = _CliOptions()
    while args:
        match args[0]:
            case "--":
                args.popleft()
                break
            case "-h" | "--help":
                print(f"USAGE: {name} {USAGE}")
                sys.exit(0)
            case "--shell":
                args.popleft()
                opts.shell = True
            case arg if arg.startswith("-"):
                _die(f"ERROR: unknown option {shlex.quote(arg)}")
            case _:
                break
    return opts


def _consume_template(
    args: collections.deque[str], *, opts: _CliOptions
) -> Sequence[str]:
    template = list[str]()
    while args:
        match args[0]:
            case ":::":
                args.popleft()
                break
            case arg:
                args.popleft()
                template.append(arg)
    if not template:
        _die("ERROR: template cannot be empty")
    if opts.shell and len(template) != 1:
        _die("ERROR: under `--shell`, the template must be a single argument")
    return template


async def _run_all_tasks(args: _CliArguments) -> dict[str, asyncio.subprocess.Process]:
    tasks: dict[str, asyncio.Task[asyncio.subprocess.Process]] = {}
    async with asyncio.TaskGroup() as tg:
        for param in args.params:
            tasks[param] = tg.create_task(
                _run(
                    *_expand_template(template=args.template, value=param),
                    shell=args.shell,
                )
            )

    return {param: task.result() for param, task in tasks.items()}


async def _run(*cmd: str, shell: bool) -> asyncio.subprocess.Process:
    if shell and len(cmd) != 1:
        raise TypeError
    if shell:
        _warn(f"{BOLD}{cmd[0]}{NORMAL}")
        p = await asyncio.subprocess.create_subprocess_shell(cmd[0])
    else:
        _warn(f"{BOLD}{shlex.join(cmd)}{NORMAL}")
        p = await asyncio.subprocess.create_subprocess_exec(*cmd)
    await p.wait()
    return p


def _expand_template(*, template: Sequence[str], value: str) -> Sequence[str]:
    return tuple(arg.replace("{}", value) for arg in template)


if __name__ == "__main__":
    asyncio.run(main())
