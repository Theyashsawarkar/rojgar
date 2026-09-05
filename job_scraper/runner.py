"""End-to-end orchestration: run every enabled scraper, filter to what
actually matches the user's constraints, dedupe against what's already
logged (and within this batch), and append the rest to jobs.db. The
one place that wires config + scrapers + filtering + db together.
"""
from __future__ import annotations

from pathlib import Path

from . import db, ui
from .config import Config
from .filtering import dedup_new_jobs, filter_jobs
from .scrapers import SCRAPERS

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_db_path(config: Config) -> Path:
    db_path = Path(config.db_path)
    return db_path if db_path.is_absolute() else PROJECT_ROOT / db_path


def run(config: Config) -> None:
    db_path = resolve_db_path(config)

    all_jobs = []
    for name in config.sources:
        scraper_cls = SCRAPERS.get(name)
        if scraper_cls is None:
            print(ui.warn(f"  ⚠️  unknown source '{name}' in config -- skipping"))
            continue
        print(ui.bold(f"Searching {name}..."))
        try:
            found = scraper_cls().search(config)
        except Exception as error:
            # One source misbehaving (a schema change, a timeout that
            # slips past requests' own handling, etc.) shouldn't take
            # the whole run down with it.
            print(ui.warn(f"  ⚠️  {name}: unexpected error, skipping this source: {error}"))
            continue
        print(ui.dim(f"  found {len(found)} listing(s)"))
        all_jobs.extend(found)

    matched = filter_jobs(all_jobs, config)
    print(ui.info(f"\n{len(matched)} of {len(all_jobs)} listing(s) match your keywords/salary/location."))

    conn = db.connect(db_path)
    keys = db.existing_keys(conn, config.dedup_strategy)
    new_jobs = dedup_new_jobs(matched, keys, config.dedup_strategy)
    db.append_jobs(conn, new_jobs)
    conn.close()

    already_logged = len(matched) - len(new_jobs)
    summary = f"Added {len(new_jobs)} new job(s) to {db_path.name} ({already_logged} already logged)."
    print(ui.success(summary) if new_jobs else ui.dim(summary))
    if new_jobs:
        print(ui.dim("View them with: rojgar ui"))
