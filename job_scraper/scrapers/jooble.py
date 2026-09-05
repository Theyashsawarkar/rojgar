"""Jooble -- a real, sanctioned job search API. Requires a free API
key: register at https://jooble.org/api/about (they email you a key).

Jooble's docs page requires registration to view the actual field
reference, so the shape below follows their long-standing, widely
documented public format (POST to jooble.org/api/{key} with a
{"keywords", "location"} body, a {"jobs": [...]} response) rather than
a live-verified response. If your first real run comes back empty or
looks wrong, print the raw JSON here and adjust the field names below
against it -- everything else in this project (Remotive, RemoteOK) was
built against a live response; this one couldn't be, for lack of a key.
"""
from __future__ import annotations

import requests

from ..config import Config
from ..models import Job
from .base import JobScraper

API_URL = "https://jooble.org/api/{key}"


class JoobleScraper(JobScraper):
    name = "jooble"

    def search(self, config: Config) -> list[Job]:
        if not config.jooble_api_key:
            print("  ℹ️  jooble: skipped -- no API key set (see README for how to get a free one)")
            return []

        jobs: list[Job] = []
        seen_urls: set[str] = set()
        for keyword in config.tech_stack or [""]:
            body = {"keywords": keyword, "location": config.city}
            try:
                response = requests.post(API_URL.format(key=config.jooble_api_key), json=body, timeout=15)
                response.raise_for_status()
            except requests.RequestException as error:
                print(f"  ⚠️  jooble: request failed for '{keyword}': {error}")
                continue

            for raw in response.json().get("jobs", []):
                url = raw.get("link", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                jobs.append(
                    Job(
                        source=self.name,
                        company=(raw.get("company") or "").strip(),
                        title=(raw.get("title") or "").strip(),
                        apply_link=url,
                        location=(raw.get("location") or "").strip(),
                        salary_raw=raw.get("salary") or "",
                        requirements=(raw.get("snippet") or "").strip(),
                    )
                )
        return jobs
