"""Best-effort salary parsing.

Job postings write salary in every format imaginable -- "4-6 LPA",
"₹4,00,000 - 6,00,000 per annum", "40k/month", "$50,000 - $70,000",
"Not disclosed". This module normalizes whatever it can confidently
parse into a (min_lpa, max_lpa) range and returns None for anything it
can't -- a job with an unparseable salary is still kept and shown with
its raw text, never dropped just because parsing failed.
"""
from __future__ import annotations

import re

_UNDISCLOSED = re.compile(r"not\s*disclosed|confidential|undisclosed|competitive", re.I)
_NUMBER = re.compile(r"[\d,]+(?:\.\d+)?")
# $1 = ~₹83 (approximate, only used for a rough estimate), divided by
# 100,000 to land in Lakhs directly -- e.g. $50,000/yr -> 50000 * 83 /
# 100000 = 41.5 LPA. (Caught live: an earlier version of this constant
# was off by 100x, computing $50k/yr as "4150 LPA" -- verified by
# testing real example strings before trusting this, not just reading
# the formula and assuming it was right.)
_USD_ANNUAL_TO_LPA = 83 / 100_000


def _numbers(text: str) -> list[float]:
    return [float(m.replace(",", "")) for m in _NUMBER.findall(text)]


def parse_salary_lpa(raw: str) -> tuple[float, float] | None:
    """Returns (min, max) in Lakhs Per Annum, or None if unparseable."""
    if not raw or not raw.strip():
        return None
    text = raw.strip().lower()
    if _UNDISCLOSED.search(text):
        return None

    nums = _numbers(text)
    if not nums:
        return None

    is_usd = "$" in text or "usd" in text
    is_monthly = bool(re.search(r"/\s*mo|per\s*month|monthly|/\s*month", text))
    is_lpa = bool(re.search(r"lpa|lakh|lac", text))
    has_k = bool(re.search(r"\bk\b|\d+k(?!\w)", text))

    if is_lpa:
        values = nums
    elif is_usd:
        # "k" here means thousands of dollars/year (the common USD
        # posting shorthand, "$50k-70k") -- monthly USD postings are
        # rare enough in this data that they're left unparsed rather
        # than guessed at.
        multiplier = 1000 if has_k else 1
        values = [n * multiplier * _USD_ANNUAL_TO_LPA for n in nums]
    elif is_monthly:
        multiplier = 1000 if has_k else 1
        values = [(n * multiplier * 12) / 100_000 for n in nums]
    elif has_k:
        # Bare "k" with no currency/period marker, e.g. "40-50k" --
        # the common Indian-market shorthand for monthly INR.
        values = [(n * 1000 * 12) / 100_000 for n in nums]
    else:
        # Bare numbers with a ₹ sign or nothing at all. Anything under
        # 100 is almost certainly already meant as LPA ("4-6" with no
        # unit at all); anything larger is treated as a raw annual
        # rupee figure.
        values = [n if n < 100 else n / 100_000 for n in nums]

    if not values:
        return None
    return (round(min(values), 2), round(max(values), 2))


def in_range(raw: str, target_min: float, target_max: float) -> bool | None:
    """True/False if the parsed range overlaps [target_min, target_max],
    None if the salary couldn't be parsed at all (caller decides whether
    to keep unparseable-salary jobs or not -- see config.py)."""
    parsed = parse_salary_lpa(raw)
    if parsed is None:
        return None
    lo, hi = parsed
    return lo <= target_max and hi >= target_min
