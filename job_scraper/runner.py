"""End-to-end orchestration: run every enabled scraper, filter to what
actually matches the user's constraints, dedupe against what's already
logged (and within this batch), and append the rest to the Excel
sheet. The one place that wires config + scrapers + filtering +
excel_store together.
"""
from __future__ import annotations

from pathlib import Path

from . import ui
from .config import Config
from .excel_store import append_jobs, existing_keys, load_or_create, save
from .filtering import dedup_new_jobs, filter_jobs
from .scrapers import SCRAPERS

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run(config: Config) -> None:
    output_path = Path(config.output_path)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    all_jobs = []
    for name in config.sources:
        scraper_cls = SCRAPERS.get(name)
        if scraper_cls is None:
            print(f"  ⚠️  unknown source '{name}' in config -- skipping")
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

    wb = load_or_create(output_path)
    keys = existing_keys(wb, config.dedup_strategy)
    new_jobs = dedup_new_jobs(matched, keys, config.dedup_strategy)

    append_jobs(wb, new_jobs)
    save(wb, output_path)

    already_logged = len(matched) - len(new_jobs)
    summary = f"Added {len(new_jobs)} new job(s) to {output_path.name} ({already_logged} already logged)."
    print(ui.success(summary) if new_jobs else ui.dim(summary))
