"""Small text-cleanup helpers shared by more than one scraper -- kept
here instead of duplicated per-file."""
from __future__ import annotations

import re

_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")

# Locations that mean "not tied to a specific place" -- these should
# never be geocoded or radius-filtered against; treated as unknown
# location instead (see filtering.matches_location's
# include_unknown_location default).
_LOCATION_AGNOSTIC = {"worldwide", "anywhere", "remote", "global"}


def strip_html(text: str, max_length: int = 500) -> str:
    """Plain text from an HTML description -- good enough for a
    spreadsheet cell, not meant to preserve formatting."""
    if not text:
        return ""
    plain = _TAG.sub(" ", text)
    plain = _WHITESPACE.sub(" ", plain).strip()
    if len(plain) > max_length:
        plain = plain[: max_length - 1].rstrip() + "…"
    return plain


def normalize_location(raw: str) -> str:
    """Empty string for anything location-agnostic (Worldwide, Remote,
    etc.) so it falls through to "unknown location" handling instead
    of being geocoded as a literal place called "Worldwide"."""
    if not raw:
        return ""
    if raw.strip().lower() in _LOCATION_AGNOSTIC:
        return ""
    return raw.strip()
