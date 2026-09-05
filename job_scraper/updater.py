"""`rojgar --update` -- fetches the GitHub repo this install came from
and, if origin has moved on, fast-forwards the local checkout and
reinstalls. Never force-resets: a dirty working tree or a history that
can't fast-forward stops the update with a clear message instead of
silently discarding local changes.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import ui

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=PROJECT_ROOT, capture_output=True, text=True)


def _pip_path() -> Path:
    for candidate in (
        PROJECT_ROOT / ".venv" / "bin" / "pip",
        PROJECT_ROOT / ".venv" / "Scripts" / "pip.exe",
    ):
        if candidate.exists():
            return candidate
    return Path("pip")


def check_and_update() -> None:
    if not (PROJECT_ROOT / ".git").exists():
        print(ui.warn("This install isn't a git checkout -- can't self-update."))
        print("Reinstall from https://github.com/Theyashsawarkar/rojgar instead.")
        return

    dirty = _run(["git", "status", "--porcelain"])
    if dirty.stdout.strip():
        print(ui.warn("You have uncommitted local changes -- commit or stash them first:"))
        print(dirty.stdout)
        return

    print("Checking for updates...")
    fetch = _run(["git", "fetch", "origin"])
    if fetch.returncode != 0:
        print(ui.error(f"Couldn't reach GitHub: {fetch.stderr.strip()}"))
        return

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    local = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    remote = _run(["git", "rev-parse", f"origin/{branch}"]).stdout.strip()

    if local == remote:
        print(ui.success("Already up to date."))
        return

    print(f"Update available on '{branch}' -- pulling...")
    pull = _run(["git", "pull", "--ff-only", "origin", branch])
    if pull.returncode != 0:
        print(ui.error("Couldn't fast-forward automatically. Update manually:"))
        print(f"  cd {PROJECT_ROOT} && git pull")
        print(pull.stderr.strip())
        return

    print("Reinstalling dependencies...")
    install = subprocess.run(
        [str(_pip_path()), "install", "--quiet", "-e", str(PROJECT_ROOT)],
        capture_output=True, text=True,
    )
    if install.returncode != 0:
        print(ui.warn("Pulled the update, but reinstalling dependencies failed:"))
        print(install.stderr.strip())
        return

    print(ui.success("Updated. Restart rojgar to use the new version."))
