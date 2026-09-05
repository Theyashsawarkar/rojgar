"""The one shared shape every scraper normalizes its results into."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Job:
    """A single job listing, normalized to a common shape regardless of
    which source it came from.

    `salary_raw` and `experience_raw` keep the original text from the
    posting -- salary/experience formats vary wildly between sources
    ("4-6 LPA", "₹40,000/month", "Not disclosed", "2+ years") and are
    parsed separately (see salary.py) rather than forced into a single
    format here, so a job with an unparseable salary still gets stored
    and shown instead of silently dropped.
    """

    source: str
    company: str
    title: str
    apply_link: str
    location: str = ""
    salary_raw: str = ""
    experience_raw: str = ""
    requirements: str = ""
    tags: list[str] = field(default_factory=list)

    def dedup_key(self, strategy: str) -> str:
        """A stable, case-insensitive key for "have I already seen this
        job" comparisons. `strategy` matches config.DEDUP_CHOICES."""
        title_company = f"{self.company.strip().lower()}|{self.title.strip().lower()}"
        if strategy == "url":
            return self.apply_link.strip().lower()
        if strategy == "both":
            return f"{title_company}|{self.apply_link.strip().lower()}"
        return title_company
