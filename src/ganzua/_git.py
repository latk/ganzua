import dataclasses
import os
import shlex
import subprocess
import typing as t

_ENV_PREDICTABLE_COMMIT = {
    "GIT_AUTHOR_NAME": "example",
    "GIT_AUTHOR_EMAIL": "example@example.com",
    "GIT_AUTHOR_DATE": "2026-01-01 00:00:00Z",
    "GIT_COMMITTER_NAME": "example",
    "GIT_COMMITTER_EMAIL": "example@example.com",
    "GIT_COMMITTER_DATE": "2026-01-01 00:00:00Z",
}

# Suppress the default Git configs by setting them to `/dev/null`.
# <https://git-scm.com/docs/git#Documentation/git.txt-GITCONFIGGLOBAL>
_ENV_PREDICTABLE_CONFIG = {
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "LC_ALL": "C.UTF-8",  # avoid localization problems
}


class RunArgs(t.TypedDict, total=False):
    """Supported args for `subprocess.run()`."""

    check: t.Required[bool]
    stdout: t.IO | int
    stderr: t.IO | int
    text: bool
    cwd: str


@dataclasses.dataclass
class Git:
    exe: str = "git"
    _: dataclasses.KW_ONLY
    predictable_commit: bool = False
    predictable_config: bool = False

    def read_blob(
        self,
        blob_name: str,
        *,
        mkerr: t.Callable[[str], Exception | t.Never],
    ) -> str:
        result = subprocess.run(
            [self.exe, "cat-file", "blob", blob_name],
            stdout=subprocess.PIPE,
            text=True,
            check=False,
            env=self._effective_env(),
        )
        if result.returncode:
            msg = f"Could not read file from Git history: `{blob_name}`"
            msg += f"\nNote: Command `{shlex.join(result.args)}` exited with status {result.returncode}"
            raise mkerr(msg)
        return result.stdout

    def run(
        self, command: t.Sequence[str], **kwargs: t.Unpack[RunArgs]
    ) -> subprocess.CompletedProcess:
        return subprocess.run([self.exe, *command], **kwargs, env=self._effective_env())

    def _effective_env(self) -> t.Mapping[str, str] | None:
        override = dict[str, str]()
        if self.predictable_config:
            override |= _ENV_PREDICTABLE_CONFIG
        if self.predictable_commit:
            override |= _ENV_PREDICTABLE_COMMIT
        if override:
            return os.environ | override
        return None
