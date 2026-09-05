"""Local single-user login for the web dashboard. One row in `users`
at a time -- this is a personal tool, not a multi-tenant app -- so
setting a new password (via `rojgar auth`) simply replaces it.
"""
from __future__ import annotations

import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash


def has_user(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


def set_password(conn: sqlite3.Connection, username: str, password: str) -> None:
    conn.execute("DELETE FROM users")
    conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, generate_password_hash(password)),
    )
    conn.commit()


def verify(conn: sqlite3.Connection, username: str, password: str) -> bool:
    row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
    return row is not None and check_password_hash(row["password_hash"], password)
