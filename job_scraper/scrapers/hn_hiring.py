"""Hacker News monthly "Who is hiring?" threads, via the free, public,
no-key Algolia HN Search API (hn.algolia.com/api). Unlike the other
sources, a "job" here is one raw, unstructured top-level comment --
there's no separate title/company/salary fields to read, posters just
write free text (often "Company | Location | Role" on the first line,
but not consistently). Company/title are a best-effort guess at that
first line; the full comment goes into `requirements` so filtering.py's
keyword match still works against the real content either way.
"""
from __future__ import annotations

import html
import re

import requests

from ..config import Config
from ..models import Job
from .base import JobScraper

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = html.unescape(text or "")
    text = _TAG.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def _latest_hiring_thread_id() -> str | None:
    try:
        response = requests.get(
            SEARCH_URL,
            params={"tags": "story,author_whoishiring", "hitsPerPage": 10},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None
    for hit in response.json().get("hits", []):
        if "who is hiring" in (hit.get("title") or "").lower():
            return hit.get("objectID")
    return None


class HNHiringScraper(JobScraper):
    name = "hn_hiring"

    def search(self, config: Config) -> list[Job]:
        thread_id = _latest_hiring_thread_id()
        if thread_id is None:
            print("  ⚠️  hn_hiring: couldn't find the latest 'Who is hiring?' thread")
            return []

        jobs: list[Job] = []
        page = 0
        while True:
            try:
                response = requests.get(
                    SEARCH_URL,
                    params={"tags": f"comment,story_{thread_id}", "hitsPerPage": 500, "page": page},
                    timeout=15,
                )
                response.raise_for_status()
            except requests.RequestException as error:
                print(f"  ⚠️  hn_hiring: request failed: {error}")
                break

            data = response.json()
            for hit in data.get("hits", []):
                # Only top-level comments are job posts -- replies
                # nested under them are discussion, not new listings.
                if str(hit.get("parent_id")) != str(thread_id):
                    continue
                text = _clean(hit.get("comment_text", ""))
                if not text:
                    continue
                first_line = text.split(". ")[0][:120]
                company = first_line.split("|")[0].strip() if "|" in first_line else first_line
                jobs.append(
                    Job(
                        source=self.name,
                        company=company or "Unknown",
                        title=first_line,
                        apply_link=f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                        requirements=text,
                    )
                )

            if page + 1 >= data.get("nbPages", 1):
                break
            page += 1
        return jobs
