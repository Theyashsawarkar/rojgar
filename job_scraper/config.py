"""User preferences: interactive first-run setup, saved to a static
JSON file in the repo (config.json) so later runs never ask again --
CLI flags (see cli.py) can still override any single field per-run
without touching the saved file.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import ui

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEDUP_CHOICES = ("title_company", "url", "both")
RUN_PATTERN_CHOICES = ("manual", "scheduled")

# Every scraper module registers its own NAME here (see scrapers/__init__.py)
# -- kept here too, as a plain tuple, so config.py has zero import
# dependency on the scrapers package (avoids a circular import, since
# scrapers/base.py doesn't need to know about config at all).
KNOWN_SOURCES = ("remotive", "remoteok", "adzuna", "jooble", "hn_hiring")


@dataclass
class Config:
    tech_stack: list[str] = field(default_factory=list)
    city: str = ""
    radius_km: float = 500.0
    salary_target_lpa: float | None = None
    salary_buffer_lpa: float = 1.0
    experience_years: str = ""
    dedup_strategy: str = "title_company"
    include_unknown_salary: bool = True
    include_unknown_location: bool = True
    output_path: str = "jobs.xlsx"
    run_pattern: str = "manual"
    schedule_interval_hours: int | None = 24
    sources: list[str] = field(default_factory=lambda: list(KNOWN_SOURCES))
    # Adzuna and Jooble require a free API key (real, sanctioned APIs,
    # not scraped) -- left blank means that specific source is silently
    # skipped rather than the whole run failing, with a note printed
    # once per run so it's not a silent gap.
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jooble_api_key: str = ""

    @property
    def salary_range(self) -> tuple[float, float] | None:
        if self.salary_target_lpa is None:
            return None
        return (
            max(0.0, self.salary_target_lpa - self.salary_buffer_lpa),
            self.salary_target_lpa + self.salary_buffer_lpa,
        )


def load() -> Config | None:
    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    known_fields = {f for f in Config.__dataclass_fields__}
    return Config(**{k: v for k, v in data.items() if k in known_fields})


def save(config: Config) -> None:
    CONFIG_PATH.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False) + "\n")


def _ask(prompt: str, default: str = "") -> str:
    suffix = ui.dim(f" [{default}]") if default else ""
    answer = input(f"{ui.bold(prompt)}{suffix}: ").strip()
    return answer if answer else default


def _ask_float(prompt: str, default: float) -> float:
    while True:
        raw = _ask(prompt, str(default))
        try:
            return float(raw)
        except ValueError:
            print(ui.warn("  Please enter a number."))


def _ask_optional_float(prompt: str) -> float | None:
    raw = _ask(f"{prompt} (leave blank for no preference)", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        print("  Couldn't read that as a number -- skipping.")
        return None


def _ask_choice(prompt: str, choices: tuple[str, ...], default: str) -> str:
    while True:
        raw = _ask(f"{prompt} ({'/'.join(choices)})", default)
        if raw in choices:
            return raw
        print(ui.warn(f"  Please pick one of: {', '.join(choices)}"))


def run_interactive_setup() -> Config:
    """One question at a time, sane defaults on everything, most
    fields skippable with a bare Enter. Ends by writing config.json so
    this never runs again unless the user explicitly re-runs `configure`."""
    print(ui.heading("Let's set up your job search preferences") + ui.dim(" (one-time -- saved to"))
    print(ui.dim(f"{CONFIG_PATH.name}, edit that file directly or run 'configure' again to change these later).\n"))

    tech_stack_raw = _ask("Tech stack / keywords, comma-separated (e.g. Python, React, Django)")
    tech_stack = [t.strip() for t in tech_stack_raw.split(",") if t.strip()]

    city = _ask("Which city are you targeting?")

    radius_km = _ask_float(
        "Search radius around that city, in km (jobs listed further away are excluded)",
        500.0,
    )

    salary_target = _ask_optional_float("Target salary, in LPA (Lakhs Per Annum)")
    salary_buffer = 1.0
    if salary_target is not None:
        salary_buffer = _ask_float(
            f"Salary range buffer -- shows jobs from {salary_target - 1:g} to "
            f"{salary_target + 1:g} LPA by default, change the ± amount",
            1.0,
        )

    experience_years = _ask("Years of experience (e.g. '2-4', '5+', or blank for any)")

    dedup_strategy = _ask_choice(
        "How should duplicate jobs be detected across runs",
        DEDUP_CHOICES,
        "title_company",
    )

    run_pattern = _ask_choice(
        "Run manually each time, or set up a recurring schedule",
        RUN_PATTERN_CHOICES,
        "manual",
    )
    schedule_interval_hours = 24
    if run_pattern == "scheduled":
        schedule_interval_hours = int(_ask_float("Check every how many hours", 24))

    config = Config(
        tech_stack=tech_stack,
        city=city,
        radius_km=radius_km,
        salary_target_lpa=salary_target,
        salary_buffer_lpa=salary_buffer,
        experience_years=experience_years,
        dedup_strategy=dedup_strategy,
        run_pattern=run_pattern,
        schedule_interval_hours=schedule_interval_hours,
    )
    save(config)
    print(ui.success(f"\nSaved to {CONFIG_PATH}.") + f" Run {ui.bold('rojgar run')} any time, or {ui.bold('rojgar configure')} to change these again.\n")
    return config
