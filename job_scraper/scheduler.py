"""Recurring runs via a systemd --user timer -- covers the "or he can
configure it in the config file" half of the run-pattern requirement:
`schedule --install` reads schedule_interval_hours straight out of the
saved config.json, so changing that file and re-running --install is
all that's needed to change the cadence, no code edits required.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_NAME = "job-scraper.service"
TIMER_NAME = "job-scraper.timer"


def _venv_python() -> Path:
    candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def install(config: Config) -> None:
    interval = config.schedule_interval_hours or 24
    UNIT_DIR.mkdir(parents=True, exist_ok=True)

    (UNIT_DIR / SERVICE_NAME).write_text(
        "[Unit]\n"
        "Description=job-scraper -- search for new job listings\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"WorkingDirectory={PROJECT_ROOT}\n"
        f"ExecStart={_venv_python()} -m job_scraper run\n"
    )
    (UNIT_DIR / TIMER_NAME).write_text(
        "[Unit]\n"
        "Description=Run job-scraper on a schedule\n\n"
        "[Timer]\n"
        f"OnBootSec=5min\n"
        f"OnUnitActiveSec={interval}h\n"
        "Persistent=true\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", TIMER_NAME], check=True)
    print(f"Installed -- job-scraper will run every {interval} hour(s) via systemd --user.")
    print("Note: this only fires while you're logged in unless lingering is enabled --")
    print(f"run 'loginctl enable-linger {Path.home().name}' for it to run even when logged out.")
    print("Check it any time with: job-scraper schedule --status")


def uninstall() -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", TIMER_NAME], check=False)
    for name in (SERVICE_NAME, TIMER_NAME):
        path = UNIT_DIR / name
        if path.exists():
            path.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print("Removed the scheduled run.")


def status() -> None:
    if not (UNIT_DIR / TIMER_NAME).exists():
        print("Not installed. Run: job-scraper schedule --install")
        return
    subprocess.run(["systemctl", "--user", "status", TIMER_NAME, "--no-pager"], check=False)
