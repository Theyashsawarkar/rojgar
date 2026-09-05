"""RemoteOK (remoteok.com) -- a real, free, public JSON API, no key
needed. Per their API terms: results must credit "Remote OK" as the
source and link back to remoteok.com (both true here -- see README).
"""
from __future__ import annotations

import requests

from .. import ui
from ..config import Config
from ..models import Job
from ..text_utils import normalize_location, strip_html
from .base import JobScraper

API_URL = "https://remoteok.com/api"


class RemoteOKScraper(JobScraper):
    name = "remoteok"

    def search(self, config: Config) -> list[Job]:
        try:
            response = requests.get(API_URL, headers={"User-Agent": "job-scraper/1.0"}, timeout=15)
            response.raise_for_status()
            entries = response.json()
        except requests.RequestException as error:
            print(ui.warn(f"  ⚠️  remoteok: request failed: {error}"))
            return []

        jobs: list[Job] = []
        # entries[0] is always an API-terms/legal notice, not a real
        # job -- confirmed live, not assumed from the docs.
        for raw in entries[1:]:
            salary_min, salary_max = raw.get("salary_min") or 0, raw.get("salary_max") or 0
            salary_raw = f"${salary_min:,} - ${salary_max:,}" if salary_min or salary_max else ""
            jobs.append(
                Job(
                    source=self.name,
                    company=(raw.get("company") or "").strip(),
                    title=(raw.get("position") or "").strip(),
                    apply_link=raw.get("apply_url") or raw.get("url") or "",
                    location=normalize_location(raw.get("location") or ""),
                    salary_raw=salary_raw,
                    requirements=strip_html(raw.get("description") or ""),
                    tags=raw.get("tags") or [],
                )
            )
        return jobs
