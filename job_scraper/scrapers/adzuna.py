"""Adzuna -- a real, sanctioned job search API with a country-specific
endpoint for India (/in/), which is what actually makes this source
India-*specific* rather than just remote-global (see remotive.py /
remoteok.py). Requires a free API key: register at
https://developer.adzuna.com/ for an app_id + app_key, then put them
in config.json (or pass --adzuna-app-id/--adzuna-app-key per run).
"""
from __future__ import annotations

import requests

from ..config import Config
from ..models import Job
from ..text_utils import normalize_location, strip_html
from .base import JobScraper

API_URL = "https://api.adzuna.com/v1/api/jobs/in/search/{page}"
_RESULTS_PER_PAGE = 50
_MAX_PAGES = 2


class AdzunaScraper(JobScraper):
    name = "adzuna"

    def search(self, config: Config) -> list[Job]:
        if not config.adzuna_app_id or not config.adzuna_app_key:
            print("  ℹ️  adzuna: skipped -- no API key set (see README for how to get a free one)")
            return []

        jobs: list[Job] = []
        seen_urls: set[str] = set()
        for keyword in config.tech_stack or [""]:
            for page in range(1, _MAX_PAGES + 1):
                params = {
                    "app_id": config.adzuna_app_id,
                    "app_key": config.adzuna_app_key,
                    "what": keyword,
                    "results_per_page": _RESULTS_PER_PAGE,
                    "content-type": "application/json",
                }
                if config.city:
                    params["where"] = config.city
                try:
                    response = requests.get(API_URL.format(page=page), params=params, timeout=15)
                    response.raise_for_status()
                except requests.RequestException as error:
                    print(f"  ⚠️  adzuna: request failed for '{keyword}' page {page}: {error}")
                    break

                results = response.json().get("results", [])
                if not results:
                    break
                for raw in results:
                    url = raw.get("redirect_url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    salary_min, salary_max = raw.get("salary_min"), raw.get("salary_max")
                    # Adzuna gives raw annual rupee figures, not LPA --
                    # left as bare numbers here on purpose, since
                    # salary.py's fallback branch (numbers >= 100 are
                    # treated as raw rupees / 100,000) already handles
                    # this correctly without source-specific logic.
                    salary_raw = f"{salary_min:.0f} - {salary_max:.0f}" if salary_min and salary_max else ""
                    jobs.append(
                        Job(
                            source=self.name,
                            company=((raw.get("company") or {}).get("display_name") or "").strip(),
                            title=(raw.get("title") or "").strip(),
                            apply_link=url,
                            location=normalize_location((raw.get("location") or {}).get("display_name") or ""),
                            salary_raw=salary_raw,
                            requirements=strip_html(raw.get("description") or ""),
                        )
                    )
        return jobs
