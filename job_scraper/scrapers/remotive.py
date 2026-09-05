"""Remotive (remotive.com) -- a real, free, public JSON API, no key
needed. Remote-first listings, which is exactly why they're relevant
to an India-based search: "remote" jobs are open to India regardless
of where the company itself is based.
"""
from __future__ import annotations

import requests

from ..config import Config
from ..models import Job
from ..text_utils import normalize_location, strip_html
from .base import JobScraper

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveScraper(JobScraper):
    name = "remotive"

    def search(self, config: Config) -> list[Job]:
        jobs: list[Job] = []
        seen_urls: set[str] = set()
        # One request per keyword -- Remotive's own `search` is a broad
        # match (confirmed live: searching "python" surfaced unrelated
        # roles too), so this is just a wide net; filtering.py does the
        # real, precise keyword matching afterward.
        for keyword in config.tech_stack or [""]:
            try:
                response = requests.get(API_URL, params={"search": keyword}, timeout=15)
                response.raise_for_status()
            except requests.RequestException as error:
                print(f"  ⚠️  remotive: request failed for '{keyword}': {error}")
                continue

            for raw in response.json().get("jobs", []):
                url = raw.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                jobs.append(
                    Job(
                        source=self.name,
                        company=raw.get("company_name", "").strip(),
                        title=raw.get("title", "").strip(),
                        apply_link=url,
                        location=normalize_location(raw.get("candidate_required_location", "")),
                        salary_raw=raw.get("salary", "") or "",
                        requirements=strip_html(raw.get("description", "")),
                        tags=raw.get("tags", []) or [],
                    )
                )
        return jobs
