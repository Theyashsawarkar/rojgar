"""Registry mapping each source name (as used in Config.sources and
config.KNOWN_SOURCES) to its scraper class. Add a new source by
writing one file in this package with a JobScraper subclass, then
adding one line here.
"""
from __future__ import annotations

from .adzuna import AdzunaScraper
from .hn_hiring import HNHiringScraper
from .jooble import JoobleScraper
from .remoteok import RemoteOKScraper
from .remotive import RemotiveScraper

SCRAPERS = {
    "remotive": RemotiveScraper,
    "remoteok": RemoteOKScraper,
    "adzuna": AdzunaScraper,
    "jooble": JoobleScraper,
    "hn_hiring": HNHiringScraper,
}
