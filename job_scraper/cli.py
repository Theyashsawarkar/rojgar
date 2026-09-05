"""Command-line interface: `rojgar run`, `rojgar configure`,
`rojgar schedule`, `rojgar ui`, `rojgar auth`. Every Config field can
be overridden per-run with a flag on `run` (see `rojgar run --help`)
-- flags only ever apply to that one invocation, they never touch the
saved config.json.
"""
from __future__ import annotations

import argparse
import dataclasses
import getpass
import secrets
import sys
import webbrowser

from . import auth, config as config_module, db, geocoding, scheduler, ui, updater
from .config import Config
from .runner import resolve_db_path, run as run_scrapers

_DEDUP_CHOICES = config_module.DEDUP_CHOICES
_KNOWN_SOURCES = config_module.KNOWN_SOURCES


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rojgar",
        description=(
            "Finds India-relevant job listings matching your tech stack, city, "
            "salary and experience, and logs new ones to a local database so you "
            "never see the same posting twice."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "First run:\n"
            "  rojgar run                   interactive setup, then searches right away\n\n"
            "Everyday use:\n"
            "  rojgar run                   search again with your saved preferences\n"
            "  rojgar run --city Pune --radius-km 100\n"
            "                                one-off override for this run only\n"
            "  rojgar configure             redo the interactive setup from scratch\n"
            "  rojgar ui                    open the web dashboard (search/filter/mark applied)\n\n"
            "Recurring runs:\n"
            "  rojgar schedule --install    search automatically on your saved interval\n"
            "  rojgar schedule --status\n"
            "  rojgar schedule --uninstall\n\n"
            "Staying current:\n"
            "  rojgar --update              pull the latest version from GitHub and reinstall\n\n"
            "Starting over:\n"
            "  rojgar --reset               wipe config, database and cache -- fresh install state\n\n"
            "Account:\n"
            "  rojgar auth                  set/reset the username and password for the dashboard\n\n"
            "Config file: config.json in the project root (safe to edit by hand -- e.g.\n"
            "             change schedule_interval_hours, then re-run schedule --install)\n"
            "Jobs database: rojgar.db in the project root, unless --db says otherwise\n"
        ),
    )
    top_level_action = parser.add_mutually_exclusive_group()
    top_level_action.add_argument(
        "--update", action="store_true",
        help="Check GitHub for a newer version of rojgar, pull it, and reinstall dependencies",
    )
    top_level_action.add_argument(
        "--reset", action="store_true",
        help="Delete config.json, the job database, and the geocode cache, and remove any "
             "scheduled run -- the next 'rojgar run' or 'rojgar ui' starts fresh, as if just "
             "installed. Asks for confirmation first unless --yes is also given.",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip the confirmation prompt for --reset",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Search for jobs now and log new matches to the database",
        description="Search for jobs now, using your saved config.json plus any overrides below.",
    )
    run_parser.add_argument(
        "--tech-stack", metavar="LIST",
        help="Comma-separated keywords to search for, e.g. 'python,django'. Matched against each "
             "job's title, description and tags.",
    )
    run_parser.add_argument(
        "--city", metavar="CITY",
        help="Target city, e.g. 'Mumbai'. Jobs are geocoded and matched by real distance, not "
             "exact text, so nearby cities count too (see --radius-km).",
    )
    run_parser.add_argument(
        "--radius-km", type=float, metavar="KM",
        help="How far from --city a job's location may be and still count as a match (default: 500).",
    )
    run_parser.add_argument(
        "--salary-target", type=float, metavar="LPA",
        help="Target salary in Lakhs Per Annum. Jobs within --salary-buffer LPA of this are shown "
             "too, e.g. a target of 6 with the default buffer shows 5-7 LPA.",
    )
    run_parser.add_argument(
        "--salary-buffer", type=float, metavar="LPA",
        help="+/- range shown around --salary-target, in LPA (default: 1).",
    )
    run_parser.add_argument(
        "--experience", metavar="RANGE",
        help="Your experience level, free text (e.g. '2-4', '5+'). Currently informational -- "
             "stored and shown, not yet used to filter results.",
    )
    run_parser.add_argument(
        "--dedup", choices=_DEDUP_CHOICES,
        help="How a job is identified as 'already seen': 'title_company' (default), 'url', or "
             "'both' combined.",
    )
    run_parser.add_argument(
        "--sources", metavar="LIST",
        help=f"Comma-separated sources to search this run instead of your saved list. Available: "
             f"{', '.join(_KNOWN_SOURCES)}.",
    )
    run_parser.add_argument(
        "--db", metavar="PATH", help="SQLite database file to write matches to (default: rojgar.db).",
    )
    run_parser.add_argument(
        "--adzuna-app-id", metavar="ID", help="Adzuna API app_id, for this run only -- not saved to config.json.",
    )
    run_parser.add_argument(
        "--adzuna-app-key", metavar="KEY", help="Adzuna API app_key, for this run only -- not saved to config.json.",
    )
    run_parser.add_argument(
        "--jooble-api-key", metavar="KEY", help="Jooble API key, for this run only -- not saved to config.json.",
    )
    run_parser.add_argument(
        "--include-unknown-salary", dest="include_unknown_salary", action="store_true", default=None,
        help="Keep jobs whose salary text couldn't be parsed into a number (default: on).",
    )
    run_parser.add_argument(
        "--exclude-unknown-salary", dest="include_unknown_salary", action="store_false",
        help="Drop jobs whose salary text couldn't be parsed, instead of keeping them.",
    )
    run_parser.add_argument(
        "--include-unknown-location", dest="include_unknown_location", action="store_true", default=None,
        help="Keep jobs whose location couldn't be geocoded/matched to your city+radius (default: on).",
    )
    run_parser.add_argument(
        "--exclude-unknown-location", dest="include_unknown_location", action="store_false",
        help="Drop jobs whose location couldn't be matched, instead of keeping them.",
    )

    subparsers.add_parser(
        "configure",
        help="Redo the interactive setup and overwrite config.json",
        description="Redo the interactive setup and overwrite config.json.",
    )

    schedule_parser = subparsers.add_parser(
        "schedule",
        help="Install/remove/check a recurring background run",
        description="Manage a recurring background run (systemd --user timer on Linux, Task "
                     "Scheduler on Windows).",
    )
    schedule_group = schedule_parser.add_mutually_exclusive_group(required=True)
    schedule_group.add_argument(
        "--install", action="store_true",
        help="Install/update the recurring run, using config.json's schedule_interval_hours",
    )
    schedule_group.add_argument("--uninstall", action="store_true", help="Remove the recurring run")
    schedule_group.add_argument("--status", action="store_true", help="Show whether it's installed and active")

    ui_parser = subparsers.add_parser(
        "ui",
        help="Launch the local web dashboard to search, filter and mark jobs as applied",
        description="Launch the local web dashboard. Prompts to create a login on first use.",
    )
    ui_parser.add_argument("--host", default="127.0.0.1", metavar="HOST", help="Interface to bind to (default: 127.0.0.1, local-only)")
    ui_parser.add_argument("--port", type=int, default=5151, metavar="PORT", help="Port to serve on (default: 5151)")
    ui_parser.add_argument("--no-browser", action="store_true", help="Don't automatically open your browser")

    subparsers.add_parser(
        "auth",
        help="Set or reset the username/password used to log into the web dashboard",
        description="Set or reset the username/password used to log into the web dashboard.",
    )

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
    if args.db is not None:
        overrides["db_path"] = args.db
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


def _prompt_credentials() -> tuple[str, str]:
    username = input(ui.bold("Dashboard username") + ui.dim(" [admin]") + ": ").strip() or "admin"
    while True:
        password = getpass.getpass(ui.bold("Dashboard password") + ": ")
        confirm = getpass.getpass(ui.bold("Confirm password") + ": ")
        if password and password == confirm:
            return username, password
        print(ui.warn("Passwords didn't match (or were blank) -- try again."))


def _run_ui(config: Config, args: argparse.Namespace) -> None:
    from . import webapp  # imported lazily -- flask is only needed for this command

    db_path = resolve_db_path(config)
    conn = db.connect(db_path)
    if not auth.has_user(conn):
        print(ui.info("No dashboard login set up yet -- let's create one.\n"))
        username, password = _prompt_credentials()
        auth.set_password(conn, username, password)
        print(ui.success(f"Login saved for '{username}'.\n"))
    conn.close()

    if not config.secret_key:
        config = dataclasses.replace(config, secret_key=secrets.token_hex(32))
        config_module.save(config)

    url = f"http://{args.host}:{args.port}"
    print(ui.success(f"Starting dashboard at {url} (Ctrl+C to stop)"))
    if not args.no_browser:
        webbrowser.open(url)
    webapp.run(db_path, config.secret_key, host=args.host, port=args.port)


def _reset(args: argparse.Namespace) -> None:
    config = config_module.load()
    db_path = resolve_db_path(config) if config is not None else resolve_db_path(Config())
    targets = [config_module.CONFIG_PATH, db_path, geocoding.CACHE_PATH]
    existing = [p for p in targets if p.exists()]

    if not existing:
        print(ui.info("Nothing to reset -- no config, database, or cache found."))
        return

    print(ui.warn("This will permanently delete:"))
    for path in existing:
        print(f"  - {path}")
    print(ui.warn("Your job history and dashboard login cannot be recovered after this.\n"))

    if not args.yes:
        answer = input("Type 'reset' to confirm: ").strip()
        if answer != "reset":
            print("Cancelled -- nothing was deleted.")
            return

    scheduler.uninstall()
    for path in existing:
        path.unlink()
    print(ui.success("\nReset complete. Run 'rojgar run' or 'rojgar ui' to start fresh."))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.update:
        updater.check_and_update()
        return 0

    if args.reset:
        _reset(args)
        return 0

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "configure":
        ui.print_banner()
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

    if args.command == "auth":
        config = config_module.load() or config_module.run_interactive_setup()
        conn = db.connect(resolve_db_path(config))
        username, password = _prompt_credentials()
        auth.set_password(conn, username, password)
        conn.close()
        print(ui.success(f"Login saved for '{username}'."))
        return 0

    if args.command == "ui":
        config = config_module.load() or config_module.run_interactive_setup()
        _run_ui(config, args)
        return 0

    # args.command == "run"
    ui.print_banner()
    config = config_module.load()
    if config is None:
        print(ui.info("No saved preferences found -- let's set them up.\n"))
        config = config_module.run_interactive_setup()
    config = _apply_overrides(config, args)
    run_scrapers(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
