# job-scraper

A terminal tool that searches multiple job sources for listings matching
your tech stack, city (plus a search radius around it), salary range, and
experience level, and logs new matches to an Excel sheet -- so the same
posting never shows up twice.

## Setup

The system Python here has no `pip`/`sudo` available, so dependencies live
in a project-local virtual environment instead of anything system-wide:

```bash
cd job-scraper
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## First run

```bash
.venv/bin/python -m job_scraper run
```

The first run walks you through a one-question-at-a-time setup (tech stack,
city, radius, salary target, experience, dedup strategy, run pattern) and
saves your answers to `config.json` in the project root, so it never asks
again. Every question has a sane default -- just press Enter to accept it.

To redo the setup from scratch:

```bash
.venv/bin/python -m job_scraper configure
```

## Everyday use

```bash
.venv/bin/python -m job_scraper run
```

Searches again using your saved `config.json`. Any flag overrides that one
run only -- it never touches the saved file:

```bash
.venv/bin/python -m job_scraper run --city Pune --radius-km 100 --salary-target 8
```

Run `job-scraper run --help` for the full list of overridable flags
(tech stack, city, radius, salary target/buffer, experience, dedup
strategy, sources, output file, API keys, unknown-salary/location
handling).

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
  something already in the Excel sheet, *or* something already seen earlier
  in the same run (two sources can return the same posting).

## Recurring runs

Either edit `run_pattern`/`schedule_interval_hours` directly in
`config.json`, or choose "scheduled" during interactive setup -- then:

```bash
.venv/bin/python -m job_scraper schedule --install    # reads schedule_interval_hours from config.json
.venv/bin/python -m job_scraper schedule --status
.venv/bin/python -m job_scraper schedule --uninstall
```

This installs a `systemd --user` timer (`~/.config/systemd/user/job-scraper.*`).
It only fires while you're logged in unless you enable lingering:

```bash
loginctl enable-linger $(whoami)
```

Changing the cadence later is just: edit `schedule_interval_hours` in
`config.json`, then run `schedule --install` again.

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
  cli.py          argparse CLI: run / configure / schedule
  config.py       Config dataclass, load/save, interactive setup
  runner.py       wires scrapers + filtering + excel_store together
  filtering.py    keyword/salary/location matching, dedup
  salary.py       best-effort salary string parsing -> LPA range
  geocoding.py    Nominatim geocoding + haversine distance, disk-cached
  excel_store.py  reads/writes jobs.xlsx
  models.py       the Job dataclass every scraper returns
  text_utils.py   small shared text-cleanup helpers
  scheduler.py    systemd --user timer install/status/uninstall
  scrapers/       one file per job source, each a JobScraper subclass
```

Adding a new source is one file in `scrapers/` implementing
`JobScraper.search(config) -> list[Job]`, plus one line in
`scrapers/__init__.py`.

## Files not committed

`.venv/`, `config.json` (your personal preferences), `jobs.xlsx` (your
personal data), and `data/geocode_cache.json` (regenerates automatically)
are all gitignored -- see `.gitignore`.
