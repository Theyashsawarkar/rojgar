# Rojgar

("rojgar" -- रोजगार, Hindi for "employment") A terminal tool that searches
multiple job sources for listings matching your tech stack, city (plus a
search radius around it), salary range, and experience level, logs new
matches to a local SQLite database, and gives you a real, authenticated web
dashboard to browse and manage them -- so the same posting never shows up
twice and you're not stuck reading a spreadsheet.

```
========================================
  R O J G A R  -  Job Search Scraper
========================================
```

## Install

One command creates a project-local virtual environment, installs
everything into it, and puts a `rojgar` command on your PATH -- so you can
run it from any directory afterwards without activating anything or typing
its full path.

**Linux / macOS:**

```bash
git clone git@github.com:Theyashsawarkar/rojgar.git
cd rojgar
./scripts/install.sh
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/Theyashsawarkar/rojgar.git
cd rojgar
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

Both scripts check your Python version (3.10+ required), create the venv,
install dependencies, and link/shim the `rojgar` command onto your PATH.
Open a **new** terminal afterwards if `rojgar` isn't found right away --
PATH changes only apply to terminals opened after the change.

> The Windows installer, scheduler, and self-updater were written carefully
> but only tested on Linux in this project (no Windows machine was
> available during development). If something doesn't work as described on
> Windows, that's the first place to check -- please open an issue.

## First run

```bash
rojgar run
```

The first run walks you through a one-question-at-a-time setup (tech stack,
city, radius, salary target, experience, dedup strategy, run pattern) and
saves your answers to `config.json` in the project root, so it never asks
again. Every question has a sane default -- just press Enter to accept it.

To redo the setup from scratch: `rojgar configure`.

## Everyday use

```bash
rojgar run
```

Searches again using your saved `config.json`. Any flag overrides that one
run only -- it never touches the saved file:

```bash
rojgar run --city Pune --radius-km 100 --salary-target 8
```

Run `rojgar --help` for an overview of every command, or `rojgar run --help`
for the full list of overridable flags with an explanation of what each one
actually does (tech stack, city, radius, salary target/buffer, experience,
dedup strategy, sources, database path, API keys, unknown-salary/location
handling).

Output is colored when run in a real terminal, and automatically plain when
piped/redirected or when the `NO_COLOR` environment variable is set.

## The web dashboard

```bash
rojgar ui
```

Opens `http://127.0.0.1:5151` in your browser -- a dark, searchable table of
every job in your database, with stat cards (total / applied / not applied),
a search box, an applied/not-applied filter, and a one-click "Mark applied"
toggle, replacing the old "open jobs.xlsx and edit a cell" flow entirely.

The first time you run `rojgar ui`, it asks you to set a dashboard username
and password (stored as a salted hash in the database, never in plain
text). The dashboard only listens on `127.0.0.1` by default -- nothing
outside your machine can reach it unless you explicitly pass `--host`.

To change the login later: `rojgar auth`.

## How matching works

- **Location**: your city is geocoded once (cached to
  `data/geocode_cache.json`) and every job's location is checked against it
  with real great-circle distance -- a job in Pune matches a Mumbai search
  with a 200km+ radius, not just an exact "Mumbai" text match.
- **Salary**: if you target 6 LPA with the default ±1 buffer, jobs from
  5 to 7 LPA are shown. Salary strings come in wildly different formats
  across sources ("4-6 LPA", "$50k-70k", "40k/month", "Not disclosed") --
  `job_scraper/salary.py` does its best to normalize all of them to LPA; a
  job whose salary can't be parsed at all is still kept and shown with its
  raw text (configurable via `--include-unknown-salary` /
  `--exclude-unknown-salary`).
- **Dedup**: every job gets a dedup key from whichever strategy you chose
  (`title_company`, `url`, or `both`). A job is skipped if it matches
  something already in the database, *or* something already seen earlier
  in the same run (two sources can return the same posting).

## Recurring runs

Either edit `run_pattern`/`schedule_interval_hours` directly in
`config.json`, or choose "scheduled" during interactive setup -- then:

```bash
rojgar schedule --install    # reads schedule_interval_hours from config.json
rojgar schedule --status
rojgar schedule --uninstall
```

This uses `systemd --user` timers on Linux and Task Scheduler on Windows.

On Linux, the timer only fires while you're logged in unless you enable
lingering: `loginctl enable-linger $(whoami)`.

Changing the cadence later is just: edit `schedule_interval_hours` in
`config.json`, then run `schedule --install` again.

## Staying up to date

```bash
rojgar --update
```

Fetches this GitHub repo, and if `origin` has commits you don't have yet,
fast-forwards your local checkout and reinstalls dependencies. It never
force-resets anything -- if you have uncommitted local edits, or your
history has diverged (e.g. you changed files in place), it tells you
exactly what to do instead of discarding anything.

## Job sources

| Source | Coverage | API key needed? |
|---|---|---|
| [Remotive](https://remotive.com) | Remote-first listings (open to India) | No |
| [RemoteOK](https://remoteok.com) | Remote-first listings (open to India) | No |
| [Adzuna](https://developer.adzuna.com/) | India-specific market listings (`/in/` endpoint) | Yes, free |
| [Jooble](https://jooble.org/api/about) | Aggregated listings, India included | Yes, free |
| Hacker News "Who is hiring?" | Unstructured monthly thread, global | No |

Genuinely India-*local* boards like Naukri, Indeed, and LinkedIn don't offer
a public API and are hardened against scraping (fragile to build against and
against their Terms of Service) -- deliberately left out. **Adzuna's `/in/`
endpoint is the actual India-specific source** here; Remotive/RemoteOK are
remote-global boards that happen to be open to India-based candidates.

### Getting free API keys

- **Adzuna**: register at https://developer.adzuna.com/ for an `app_id` +
  `app_key`, then put them in `config.json` (`adzuna_app_id`,
  `adzuna_app_key`) or pass `--adzuna-app-id`/`--adzuna-app-key` per run.
- **Jooble**: register at https://jooble.org/api/about, they email you a
  key -- put it in `config.json` (`jooble_api_key`) or pass
  `--jooble-api-key` per run.

Without a key, that source is skipped with a one-line note; every other
source still runs normally.

> **Note on Jooble**: their docs page requires registration before showing
> the real field reference, so `scrapers/jooble.py` was written against
> Jooble's long-standing, publicly documented request/response shape rather
> than a live-verified response (every other scraper here was built and
> tested against a real live response). If your first real run with a key
> comes back empty, print the raw response inside `jooble.py` and adjust
> the field names against it.

**RemoteOK attribution**: per their API terms, results here credit
"RemoteOK" as the source and link back to remoteok.com.

## Project layout

```
job_scraper/
  cli.py          argparse CLI: run / configure / schedule / ui / auth, --update
  config.py       Config dataclass, load/save, interactive setup
  runner.py       wires scrapers + filtering + db together
  filtering.py    keyword/salary/location matching, dedup
  salary.py       best-effort salary string parsing -> LPA range
  geocoding.py    Nominatim geocoding + haversine distance, disk-cached
  db.py           SQLite storage for jobs
  auth.py         password hashing/verification for the dashboard login
  webapp.py       Flask app: login, dashboard, search/filter, applied-toggle
  templates/      login.html, dashboard.html
  static/         style.css, app.js
  updater.py      `rojgar --update` -- git fetch/pull + reinstall
  scheduler.py    systemd --user timer (Linux) / Task Scheduler (Windows)
  models.py       the Job dataclass every scraper returns
  text_utils.py   small shared text-cleanup helpers
  ui.py           cross-platform terminal colors/banner
  scrapers/       one file per job source, each a JobScraper subclass
scripts/
  install.sh      Linux/macOS installer -- venv + pip install -e . + PATH link
  install.ps1     Windows installer -- venv + pip install -e . + PATH link
```

Adding a new source is one file in `scrapers/` implementing
`JobScraper.search(config) -> list[Job]`, plus one line in
`scrapers/__init__.py`. The package name (`rojgar`) and console-script entry
point are declared in `pyproject.toml`.

## Files not committed

`.venv/`, `config.json` (your personal preferences and dashboard session
key), `rojgar.db` (your personal data, including your hashed dashboard
password), and `data/geocode_cache.json` (regenerates automatically) are
all gitignored -- see `.gitignore`.

<!-- test: confirms self-update fast-forward -->
