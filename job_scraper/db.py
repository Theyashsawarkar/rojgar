"""SQLite storage for jobs and the dashboard login -- replaces the
earlier Excel-based flow with a real queryable database the web
dashboard (webapp.py) reads and writes directly.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import salary as salary_module
from .models import Job

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    package TEXT,
    requirements TEXT,
    apply_link TEXT,
    is_applied INTEGER NOT NULL DEFAULT 0,
    source TEXT,
    location TEXT,
    found_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
"""


def _migrate_salary_to_package(conn: sqlite3.Connection) -> None:
    """Older databases (before the "Package" column existed) still
    have a `salary` column holding raw scraped text. Add `package`,
    backfill it by parsing each row's raw salary into an LPA figure,
    and leave the old column in place rather than trying to drop it --
    simpler and safe across SQLite versions than a column drop."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "salary" not in columns or "package" in columns:
        return
    conn.execute("ALTER TABLE jobs ADD COLUMN package TEXT")
    for row in conn.execute("SELECT id, salary FROM jobs"):
        conn.execute(
            "UPDATE jobs SET package = ? WHERE id = ?",
            (salary_module.format_package(row["salary"] or ""), row["id"]),
        )
    conn.commit()


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _migrate_salary_to_package(conn)
    return conn


def existing_keys(conn: sqlite3.Connection, dedup_strategy: str) -> set[str]:
    """Every dedup key already stored, built from a throwaway Job per
    row so the key logic lives in exactly one place (Job.dedup_key),
    not duplicated here -- same approach the old excel_store.py used."""
    keys = set()
    for row in conn.execute("SELECT company, title, apply_link FROM jobs"):
        placeholder = Job(source="", company=row["company"] or "", title=row["title"] or "", apply_link=row["apply_link"] or "")
        keys.add(placeholder.dedup_key(dedup_strategy))
    return keys


def append_jobs(conn: sqlite3.Connection, jobs: list[Job]) -> int:
    for job in jobs:
        conn.execute(
            "INSERT INTO jobs (company, title, package, requirements, apply_link, source, location) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                job.company,
                job.title,
                salary_module.format_package(job.salary_raw),
                job.requirements,
                job.apply_link,
                job.source,
                job.location,
            ),
        )
    conn.commit()
    return len(jobs)
