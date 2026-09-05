"""The interface every job source implements. A new source is just a
new file in this package with one class implementing `search()` --
see scrapers/remotive.py for the simplest real example.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..models import Job


class JobScraper(ABC):
    name: str

    @abstractmethod
    def search(self, config: Config) -> list[Job]:
        """Returns every job this source has for config.tech_stack --
        broad on purpose (this source's own best-effort keyword
        match, if it has one); the real, precise keyword/salary/
        location filtering happens once, centrally, in filtering.py,
        not repeated differently in every scraper."""
        raise NotImplementedError
