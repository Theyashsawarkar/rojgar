"""Command-line interface: `job-scraper run`, `job-scraper configure`,
`job-scraper schedule`. Every Config field can be overridden per-run
with a flag on `run` (see `job-scraper run --help`) -- flags only ever
apply to that one invocation, they never touch the saved config.json.
"""
from __future__ import annotations

import argparse
import dataclasses
import sys

from . import config as config_module
from . import scheduler
from .config import Config
from .runner import run as run_scrapers

_DEDUP_CHOICES = config_module.DEDUP_CHOICES
_KNOWN_SOURCES = config_module.KNOWN_SOURCES


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-scraper",
        description=(
            "Finds India-relevant job listings matching your tech stack, city, "
            "salary and experience, and logs new ones to an Excel sheet so you "
            "never see the same posting twice."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "First run:\n"
            "  job-scraper run                   interactive setup, then searches right away\n\n"
            "Everyday use:\n"
            "  job-scraper run                   search again with your saved preferences\n"
            "  job-scraper run --city Pune --radius-km 100\n"
            "                                     one-off override for this run only\n"
            "  job-scraper configure             redo the interactive setup from scratch\n\n"
            "Recurring runs:\n"
            "  job-scraper schedule --install    search automatically on your saved interval\n"
            "  job-scraper schedule --status\n"
            "  job-scraper schedule --uninstall\n\n"
            "Config file: job_scraper/config.json (safe to edit by hand -- e.g. change\n"
            "             schedule_interval_hours, then re-run schedule --install)\n"
            "Jobs sheet:  jobs.xlsx in the project root, unless --output says otherwise\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Search for jobs now and log new matches to the Excel sheet",
        description="Search for jobs now, using your saved config.json plus any overrides below.",
    )
    run_parser.add_argument("--tech-stack", metavar="LIST", help="Comma-separated keywords, e.g. 'python,django'")
    run_parser.add_argument("--city", metavar="CITY", help="Target city, e.g. 'Mumbai'")
    run_parser.add_argument("--radius-km", type=float, metavar="KM", help="Search radius around --city")
    run_parser.add_argument("--salary-target", type=float, metavar="LPA", help="Target salary, in Lakhs Per Annum")
    run_parser.add_argument("--salary-buffer", type=float, metavar="LPA", help="+/- range shown around --salary-target")
    run_parser.add_argument("--experience", metavar="RANGE", help="e.g. '2-4', '5+'")
    run_parser.add_argument("--dedup", choices=_DEDUP_CHOICES, help="How duplicate jobs are detected across runs")
    run_parser.add_argument(
        "--sources", metavar="LIST",
        help=f"Comma-separated sources to search this run, from: {', '.join(_KNOWN_SOURCES)}",
    )
    run_parser.add_argument("--output", metavar="PATH", help="Excel file to write to")
    run_parser.add_argument("--adzuna-app-id", metavar="ID", help="Override for this run only, not saved")
    run_parser.add_argument("--adzuna-app-key", metavar="KEY", help="Override for this run only, not saved")
    run_parser.add_argument("--jooble-api-key", metavar="KEY", help="Override for this run only, not saved")
    run_parser.add_argument(
        "--include-unknown-salary", dest="include_unknown_salary", action="store_true", default=None,
        help="Keep jobs whose salary couldn't be parsed (default: on)",
    )
    run_parser.add_argument(
        "--exclude-unknown-salary", dest="include_unknown_salary", action="store_false",
        help="Drop jobs whose salary couldn't be parsed",
    )
    run_parser.add_argument(
        "--include-unknown-location", dest="include_unknown_location", action="store_true", default=None,
        help="Keep jobs whose location couldn't be matched to your city/radius (default: on)",
    )
    run_parser.add_argument(
        "--exclude-unknown-location", dest="include_unknown_location", action="store_false",
        help="Drop jobs whose location couldn't be matched to your city/radius",
    )

    subparsers.add_parser(
        "configure",
        help="Redo the interactive setup and overwrite config.json",
        description="Redo the interactive setup and overwrite config.json.",
    )

    schedule_parser = subparsers.add_parser(
        "schedule",
        help="Install/remove/check a recurring background run (systemd --user timer)",
        description="Manage a recurring background run via a systemd --user timer.",
    )
    schedule_group = schedule_parser.add_mutually_exclusive_group(required=True)
    schedule_group.add_argument(
        "--install", action="store_true",
        help="Install/update the timer, using config.json's schedule_interval_hours",
    )
    schedule_group.add_argument("--uninstall", action="store_true", help="Remove the timer")
    schedule_group.add_argument("--status", action="store_true", help="Show whether the timer is installed and active")

    return parser


def _apply_overrides(config: Config, args: argparse.Namespace) -> Config:
    overrides = {}
    if args.tech_stack is not None:
        overrides["tech_stack"] = [t.strip() for t in args.tech_stack.split(",") if t.strip()]
    if args.city is not None:
        overrides["city"] = args.city
    if args.radius_km is not None:
        overrides["radius_km"] = args.radius_km
    if args.salary_target is not None:
        overrides["salary_target_lpa"] = args.salary_target
    if args.salary_buffer is not None:
        overrides["salary_buffer_lpa"] = args.salary_buffer
    if args.experience is not None:
        overrides["experience_years"] = args.experience
    if args.dedup is not None:
        overrides["dedup_strategy"] = args.dedup
    if args.sources is not None:
        overrides["sources"] = [s.strip() for s in args.sources.split(",") if s.strip()]
    if args.output is not None:
        overrides["output_path"] = args.output
    if args.adzuna_app_id is not None:
        overrides["adzuna_app_id"] = args.adzuna_app_id
    if args.adzuna_app_key is not None:
        overrides["adzuna_app_key"] = args.adzuna_app_key
    if args.jooble_api_key is not None:
        overrides["jooble_api_key"] = args.jooble_api_key
    if args.include_unknown_salary is not None:
        overrides["include_unknown_salary"] = args.include_unknown_salary
    if args.include_unknown_location is not None:
        overrides["include_unknown_location"] = args.include_unknown_location
    return dataclasses.replace(config, **overrides)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "configure":
        config_module.run_interactive_setup()
        return 0

    if args.command == "schedule":
        if args.install:
            config = config_module.load() or config_module.run_interactive_setup()
            scheduler.install(config)
        elif args.uninstall:
            scheduler.uninstall()
        elif args.status:
            scheduler.status()
        return 0

    # args.command == "run"
    config = config_module.load()
    if config is None:
        print("No saved preferences found -- let's set them up.\n")
        config = config_module.run_interactive_setup()
    config = _apply_overrides(config, args)
    run_scrapers(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
