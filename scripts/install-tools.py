#!/usr/bin/env python3

"""Install tools for the current platform: mdbook, lychee."""

import pathlib
import platform
import shutil
import subprocess
import sys
import tempfile
import typing as t
import urllib.request

SCRIPTS = pathlib.Path(__file__).parent
IS_WINDOWS = platform.system().lower().startswith("windows")
ARCHIVE_FORMAT = "zip" if IS_WINDOWS else "tar.gz"


def ensure_all_installed() -> None:
    """Ensure that all desired tools are installed."""
    # https://github.com/rust-lang/mdBook/releases
    mdbook = exefy(SCRIPTS / "mdbook")
    ensure_installed(
        mdbook,
        url=_mdbook_url("0.5.2", target=rust_target()),
        archive_path=exefy(pathlib.Path("mdbook")),
        is_installed=lambda: _is_installed(
            mdbook, ["--version"], expected="mdbook v0.5.2"
        ),
    )

    # https://github.com/lycheeverse/lychee/releases
    lychee = exefy(SCRIPTS / "lychee")
    ensure_installed(
        lychee,
        url=_lychee_url("0.22.0", target=rust_target()),
        archive_path=exefy(pathlib.Path("lychee")),
        is_installed=lambda: _is_installed(
            lychee, ["--version"], expected="lychee 0.22.0"
        ),
    )


def _mdbook_url(version: str, *, target: str) -> str:
    return f"https://github.com/rust-lang/mdBook/releases/download/v{version}/mdbook-v{version}-{target}.{ARCHIVE_FORMAT}"


def _lychee_url(version: str, *, target: str) -> str:
    return f"https://github.com/lycheeverse/lychee/releases/download/lychee-v{version}/lychee-{target}.{ARCHIVE_FORMAT}"


def ensure_installed(
    dest: pathlib.Path,
    *,
    url: str,
    archive_path: pathlib.Path,
    is_installed: t.Callable[[], bool],
) -> None:
    """Make sure that the `dest` path exists, else install it from the given URL."""
    if is_installed():
        return

    install_executable_from_url(url=url, archive_path=archive_path, dest=dest)

    if not is_installed():
        raise RuntimeError(f"failed to install {dest}")


def _is_installed(
    dest: pathlib.Path, check_args: tuple[str, ...] | list[str], *, expected: str
) -> bool:
    if not dest.is_file():
        return False

    output = subprocess.check_output([dest, *check_args], text=True)
    return output.strip() == expected


def install_executable_from_url(
    *, url: str, archive_path: pathlib.Path, dest: pathlib.Path
) -> None:
    """Install an executable from the archive at the URL.

    Args:
      url: what to download, must use HTTPS
      archive_path: relative path within the archive to extract
      dest: where the executable file should be put
    """
    if not url.startswith("https://"):
        raise ValueError(f"unsupported URL scheme: {url}")
    url_basename = pathlib.Path(url).name

    print(f"Installing {dest} from {url}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as raw_tmpdir:
        tempdir = pathlib.Path(raw_tmpdir)

        archive = tempdir / url_basename
        urllib.request.urlretrieve(url, filename=archive)  # noqa: S310

        shutil.unpack_archive(archive, extract_dir=tempdir, filter="data")
        shutil.move(src=tempdir / archive_path, dst=dest)


def exefy(path: pathlib.Path) -> pathlib.Path:
    """Add a `.exe` to the `path` if on Windows."""
    return path.with_suffix(".exe") if IS_WINDOWS else path


def rust_target() -> str:
    """Construct the expected Rust target for the current system.

    This depends on the current OS and CPU architecture,
    but uses different terms than the Python standard library.

    Rust documents its target triples here:
    <https://doc.rust-lang.org/nightly/rustc/platform-support.html#tier-1-with-host-tools>

    We decode the target names per the tables in:
    <https://stackoverflow.com/a/70820556>
    <https://github.com/cargo-bins/cargo-binstall/blob/2bbe0125097e55a26a8bfd366894fecb08c0f708/install-from-binstall-release.sh#L30-L56>.
    """
    match platform.machine().lower(), platform.system().lower():
        case ("arm64", "darwin"):
            return "aarch64-apple-darwin"
        case "aarch64", "linux":
            return "aarch64-unknown-linux-musl"
        case ("x86_64", "darwin"):
            return "x86_64-apple-darwin"
        case ("amd64", "windows"):
            return "x86_64-pc-windows-msvc"
        case ("x86_64", "linux"):
            return "x86_64-unknown-linux-musl"
        case other:
            raise RuntimeError(f"platform not supported: {other}")


if __name__ == "__main__":
    ensure_all_installed()
