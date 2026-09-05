"""Whether a scraped job actually matches the user's constraints --
keywords, salary range, location radius -- plus deduping against both
what's already logged and duplicates within the same scrape batch
(two sources returning the same posting is common, and checking only
against already-saved rows misses that entirely).
"""
from __future__ import annotations

import re

from . import salary as salary_module
from .config import Config
from .geocoding import within_radius
from .models import Job

# Remote postings often give a comma-separated list of eligible
# regions instead of a real place -- e.g. "LATAM, Europe, USA, Canada,
# APAC" -- which Nominatim can't geocode as a location at all, so
# within_radius() returns None ("unknown") for it. Left alone, that
# fell back to include_unknown_location's default of True, letting
# clearly non-India-eligible postings slip straight through a Mumbai
# search. If the string reads like a region list AND doesn't mention
# India (or a region that plausibly includes it), treat that as a
# real non-match instead of "unknown".
_REGION_LIST = re.compile(r"\b(usa|us|canada|latam|europe|uk|emea|australia|nz)\b", re.I)
_INDIA_INCLUSIVE = re.compile(r"\b(india|apac|asia|worldwide|anywhere|global)\b", re.I)


def matches_keywords(job: Job, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{job.title} {job.requirements} {' '.join(job.tags)}".lower()
    return any(kw.lower() in haystack for kw in keywords)


def matches_salary(job: Job, config: Config) -> bool:
    target_range = config.salary_range
    if target_range is None:
        return True
    result = salary_module.in_range(job.salary_raw, *target_range)
    if result is None:
        return config.include_unknown_salary
    return result


def matches_location(job: Job, config: Config) -> bool:
    if not config.city:
        return True
    if not job.location:
        return config.include_unknown_location
    result = within_radius(config.city, job.location, config.radius_km)
    if result is not None:
        return result
    if _REGION_LIST.search(job.location) and not _INDIA_INCLUSIVE.search(job.location):
        return False
    return config.include_unknown_location


def filter_jobs(jobs: list[Job], config: Config) -> list[Job]:
    return [
        job
        for job in jobs
        if matches_keywords(job, config.tech_stack)
        and matches_salary(job, config)
        and matches_location(job, config)
    ]


def dedup_new_jobs(jobs: list[Job], existing_keys: set[str], strategy: str) -> list[Job]:
    """Keeps only jobs whose dedup key isn't in existing_keys -- and
    not a repeat of an earlier job already kept from this same batch,
    caught live: without this, two sources returning the identical
    posting both got written to the sheet, since each was only ever
    checked against pre-existing rows, never against each other."""
    seen = set(existing_keys)
    kept = []
    for job in jobs:
        key = job.dedup_key(strategy)
        if key in seen:
            continue
        seen.add(key)
        kept.append(job)
    return kept
