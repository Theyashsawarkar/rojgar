"""The local dashboard -- a small Flask app that replaces the old
"open jobs.xlsx" flow with a searchable, filterable, browser-based
view of jobs.db, gated behind the login set up via `rojgar ui` (first
run) or `rojgar auth`.
"""
from __future__ import annotations

import functools
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from . import auth, db

_PACKAGE_DIR = Path(__file__).resolve().parent


def create_app(db_path: Path, secret_key: str) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_PACKAGE_DIR / "templates"),
        static_folder=str(_PACKAGE_DIR / "static"),
    )
    app.secret_key = secret_key

    def get_conn():
        return db.connect(db_path)

    def login_required(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            conn = get_conn()
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            if auth.verify(conn, username, password):
                session["logged_in"] = True
                return redirect(url_for("dashboard"))
            error = "Incorrect username or password."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        conn = get_conn()
        query = request.args.get("q", "").strip()
        status = request.args.get("status", "all")

        sql = "SELECT * FROM jobs"
        clauses: list[str] = []
        params: list[str] = []
        if query:
            clauses.append("(company LIKE ? OR title LIKE ? OR location LIKE ?)")
            like = f"%{query}%"
            params += [like, like, like]
        if status == "applied":
            clauses.append("is_applied = 1")
        elif status == "not_applied":
            clauses.append("is_applied = 0")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY found_at DESC"

        jobs = conn.execute(sql, params).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        applied = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_applied = 1").fetchone()[0]

        return render_template(
            "dashboard.html",
            jobs=jobs,
            query=query,
            status=status,
            total=total,
            applied=applied,
            shown=len(jobs),
        )

    @app.route("/jobs/<int:job_id>/toggle", methods=["POST"])
    @login_required
    def toggle_applied(job_id: int):
        conn = get_conn()
        conn.execute("UPDATE jobs SET is_applied = 1 - is_applied WHERE id = ?", (job_id,))
        conn.commit()
        row = conn.execute("SELECT is_applied FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return jsonify(is_applied=bool(row["is_applied"]))

    return app


def run(db_path: Path, secret_key: str, host: str = "127.0.0.1", port: int = 5151) -> None:
    create_app(db_path, secret_key).run(host=host, port=port, debug=False)
