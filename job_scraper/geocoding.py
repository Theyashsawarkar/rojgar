"""Turns a place name into (lat, lon) and measures distance between two
points -- the whole "search within N km of my city" feature.

Uses OpenStreetMap's Nominatim (nominatim.openstreetmap.org) -- free,
no API key, but its usage policy caps requests at 1/second and requires
a real User-Agent identifying the app. Every lookup is cached to disk
(data/geocode_cache.json) so a city name is only ever sent to Nominatim
once, no matter how many job postings mention it or how many times the
tool runs.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import requests

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "geocode_cache.json"
USER_AGENT = "job-scraper/1.0 (personal job search tool; contact: local use only)"
_MIN_INTERVAL_SECONDS = 1.0

_last_request_at = 0.0


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def _respect_rate_limit() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL_SECONDS:
        time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
    _last_request_at = time.monotonic()


def geocode(place: str) -> tuple[float, float] | None:
    """(lat, lon) for a place name, or None if it can't be found.
    India-biased (countrycodes=in) since that's this tool's whole
    audience -- a bare "Springfield"-type ambiguous name resolves to
    the Indian one, not a same-named town elsewhere."""
    key = place.strip().lower()
    if not key:
        return None

    cache = _load_cache()
    if key in cache:
        return tuple(cache[key]) if cache[key] else None

    _respect_rate_limit()
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1, "countrycodes": "in"},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, json.JSONDecodeError):
        return None

    if not results:
        cache[key] = None
        _save_cache(cache)
        return None

    coords = (float(results[0]["lat"]), float(results[0]["lon"]))
    cache[key] = list(coords)
    _save_cache(cache)
    return coords


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two (lat, lon) points, in km."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def within_radius(target_place: str, candidate_place: str, radius_km: float) -> bool | None:
    """True/False if candidate_place is within radius_km of
    target_place. None if either place couldn't be geocoded at all --
    callers decide separately whether to keep or drop jobs with an
    unresolvable location (see config.py's INCLUDE_UNKNOWN_LOCATION)."""
    target = geocode(target_place)
    candidate = geocode(candidate_place)
    if target is None or candidate is None:
        return None
    return haversine_km(target, candidate) <= radius_km
