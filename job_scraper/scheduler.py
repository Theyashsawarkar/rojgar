"""Recurring runs, cross-platform -- a systemd --user timer on Linux,
Windows Task Scheduler on Windows. Either way, `schedule --install`
reads schedule_interval_hours straight out of the saved config.json,
so changing that file and re-running --install is all that's needed to
change the cadence, no code edits required. This is the "or he can
configure it in the config file" half of the run-pattern requirement.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from . import ui
from .config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASK_NAME = "rojgar"

# -- Linux (systemd --user) --
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_NAME = "rojgar.service"
TIMER_NAME = "rojgar.timer"


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _venv_python() -> Path:
    for candidate in (
        PROJECT_ROOT / ".venv" / "bin" / "python",       # Linux/macOS
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",  # Windows
    ):
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def install(config: Config) -> None:
    interval = config.schedule_interval_hours or 24
    if _is_windows():
        _install_windows(interval)
    else:
        _install_systemd(interval)


def uninstall() -> None:
    _uninstall_windows() if _is_windows() else _uninstall_systemd()


def status() -> None:
    _status_windows() if _is_windows() else _status_systemd()


# -- systemd (Linux) --

def _install_systemd(interval: int) -> None:
    UNIT_DIR.mkdir(parents=True, exist_ok=True)

    (UNIT_DIR / SERVICE_NAME).write_text(
        "[Unit]\n"
        "Description=rojgar -- search for new job listings\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"WorkingDirectory={PROJECT_ROOT}\n"
        f"ExecStart={_venv_python()} -m job_scraper run\n"
    )
    (UNIT_DIR / TIMER_NAME).write_text(
        "[Unit]\n"
        "Description=Run rojgar on a schedule\n\n"
        "[Timer]\n"
        "OnBootSec=5min\n"
        f"OnUnitActiveSec={interval}h\n"
        "Persistent=true\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", TIMER_NAME], check=True)
    print(ui.success(f"Installed -- rojgar will run every {interval} hour(s) via systemd --user."))
    print("Note: this only fires while you're logged in unless lingering is enabled --")
    print(f"run 'loginctl enable-linger {Path.home().name}' for it to run even when logged out.")
    print("Check it any time with: rojgar schedule --status")


def _uninstall_systemd() -> None:
    if not (UNIT_DIR / TIMER_NAME).exists():
        return
    subprocess.run(["systemctl", "--user", "disable", "--now", TIMER_NAME], check=False, capture_output=True)
    for name in (SERVICE_NAME, TIMER_NAME):
        path = UNIT_DIR / name
        if path.exists():
            path.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, capture_output=True)
    print(ui.success("Removed the scheduled run."))


def _status_systemd() -> None:
    if not (UNIT_DIR / TIMER_NAME).exists():
        print(ui.info("Not installed. Run: rojgar schedule --install"))
        return
    subprocess.run(["systemctl", "--user", "status", TIMER_NAME, "--no-pager"], check=False)


# -- Windows Task Scheduler --

def _install_windows(interval: int) -> None:
    command = f'"{_venv_python()}" -m job_scraper run'
    subprocess.run(
        [
            "schtasks", "/Create", "/TN", TASK_NAME, "/TR", command,
            "/SC", "HOURLY", "/MO", str(interval), "/F",
        ],
        check=True,
    )
    print(ui.success(f"Installed -- rojgar will run every {interval} hour(s) via Task Scheduler."))
    print("Check it any time with: rojgar schedule --status")


def _uninstall_windows() -> None:
    query = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], check=False, capture_output=True)
    if query.returncode != 0:
        return
    subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], check=False, capture_output=True)
    print(ui.success("Removed the scheduled run."))


def _status_windows() -> None:
    result = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], check=False)
    if result.returncode != 0:
        print(ui.info("Not installed. Run: rojgar schedule --install"))
