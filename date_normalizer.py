# date_normalizer.py
#
# Deterministic normalization of date wording found in documents
# (Phase C7). The LLM may *locate* a date phrase, but turning "Q3 2023"
# or "mid-2019" into something sortable happens here, in plain code, so
# the result is repeatable, testable, and never invented.
#
# Every result keeps the original wording and states how much is known:
#
#   precision  day | month | quarter | half | year | decade | range | unknown
#   certainty  EXACT       the wording pins the date to its precision
#              APPROXIMATE "circa 1850", "early 2020", "the 1990s", "by 2025"
#              AMBIGUOUS   "03/04/2024" (day/month order unknown) -> year only
#              RELATIVE    "last year", "two weeks later" -> not normalized
#              UNKNOWN     nothing recognisable -> not normalized
#
# `start`/`end` are partial ISO strings ("2024", "2024-03", "2024-03-07")
# at the precision actually stated; a missing piece is never filled in.

from __future__ import annotations

import re
from typing import Any

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
    "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12,
    "december": 12,
}
_MONTH_ALT = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
_YEAR = r"(1[0-9]{3}|20[0-9]{2}|21[0-9]{2})"

_ISO_DAY = re.compile(rf"\b{_YEAR}-(\d{{1,2}})-(\d{{1,2}})\b")
_ISO_MONTH = re.compile(rf"\b{_YEAR}-(\d{{1,2}})\b(?!-)")
_MDY = re.compile(rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+{_YEAR}\b", re.I)
_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_ALT})\.?,?\s+{_YEAR}\b", re.I)
_MONTH_YEAR = re.compile(rf"\b({_MONTH_ALT})\.?,?\s+{_YEAR}\b", re.I)
_NUMERIC = re.compile(rf"\b(\d{{1,2}})[/.](\d{{1,2}})[/.]{_YEAR}\b")
_QUARTER = re.compile(rf"\bQ([1-4])\s*(?:of\s+)?(?:FY\s*)?{_YEAR}\b|\b{_YEAR}\s*Q([1-4])\b", re.I)
_QUARTER_WORDS = re.compile(
    rf"\b(first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter\s+(?:of\s+)?{_YEAR}\b", re.I
)
_HALF = re.compile(rf"\bH([12])\s*{_YEAR}\b|\b(first|second)\s+half\s+(?:of\s+)?{_YEAR}\b", re.I)
_DECADE = re.compile(r"\b(1[0-9]{2}0|20[0-9]0)'?s\b")
_YEAR_ONLY = re.compile(rf"\b{_YEAR}\b")
# Range separators, most specific first: a bare hyphen only separates a
# range between two years ("2019-2021") or when spaced ("May - June"),
# never inside an ISO date like "2024-03-07".
_RANGE_SEPARATORS = [
    re.compile(r"\s+(?:to|until|through|thru|and)\s+", re.I),
    re.compile(r"\s*[–—]\s*"),
    re.compile(r"\s+-\s+"),
    re.compile(r"(?<=\d{4})-(?=\d{4}\b)"),
]
_RANGE_HINT = re.compile(r"\b(between|from)\b|–|—|\bto\b|\buntil\b|\bthrough\b", re.I)
_APPROX = re.compile(
    r"\b(circa|c\.|ca\.|around|approximately|approx\.?|about|roughly|"
    r"early|mid|late|estimated|expected|planned|projected)\b",
    re.I,
)
_QUALIFIER = re.compile(r"\b(before|after|by|since|no later than|prior to)\b", re.I)
_RELATIVE = re.compile(
    r"\b(yesterday|today|tomorrow|recently|currently|now|"
    r"last|next|previous|following|ago|later|earlier|this)\b",
    re.I,
)

_QUARTER_WORD_NUM = {"first": 1, "1st": 1, "second": 2, "2nd": 2,
                     "third": 3, "3rd": 3, "fourth": 4, "4th": 4}


def _month(name: str) -> int:
    return _MONTHS[name.lower().rstrip(".")]


def _iso(year: int, month: int | None = None, day: int | None = None) -> str:
    if month is None:
        return f"{year:04d}"
    if day is None:
        return f"{year:04d}-{month:02d}"
    return f"{year:04d}-{month:02d}-{day:02d}"


def _valid(month: int, day: int | None = None) -> bool:
    if not 1 <= month <= 12:
        return False
    return day is None or 1 <= day <= 31


def _result(
    text: str,
    start: str | None,
    end: str | None,
    precision: str,
    certainty: str,
    qualifier: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "text": text,
        "start": start,
        "end": end or start,
        "precision": precision,
        "certainty": certainty,
        "qualifier": qualifier,
        "note": note,
    }


def _parse_point(text: str) -> dict[str, Any] | None:
    """Parse the most specific single date in ``text`` (no ranges)."""
    if m := _ISO_DAY.search(text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if _valid(mo, d):
            return _result(text, _iso(y, mo, d), None, "day", "EXACT")
    if m := _MDY.search(text):
        mo, d, y = _month(m.group(1)), int(m.group(2)), int(m.group(3))
        if _valid(mo, d):
            return _result(text, _iso(y, mo, d), None, "day", "EXACT")
    if m := _DMY.search(text):
        d, mo, y = int(m.group(1)), _month(m.group(2)), int(m.group(3))
        if _valid(mo, d):
            return _result(text, _iso(y, mo, d), None, "day", "EXACT")
    if m := _NUMERIC.search(text):
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 and _valid(b, a):
            return _result(text, _iso(y, b, a), None, "day", "EXACT")
        if b > 12 and _valid(a, b):
            return _result(text, _iso(y, a, b), None, "day", "EXACT")
        if a == b and _valid(a, b):
            return _result(text, _iso(y, a, b), None, "day", "EXACT")
        return _result(
            text, _iso(y), None, "year", "AMBIGUOUS",
            note="Day/month order is ambiguous; only the year is used.",
        )
    if m := _QUARTER.search(text):
        q = int(m.group(1) or m.group(4))
        y = int(m.group(2) or m.group(3))
        return _result(text, _iso(y, 3 * q - 2), _iso(y, 3 * q), "quarter", "EXACT")
    if m := _QUARTER_WORDS.search(text):
        q = _QUARTER_WORD_NUM[m.group(1).lower()]
        y = int(m.group(2))
        return _result(text, _iso(y, 3 * q - 2), _iso(y, 3 * q), "quarter", "EXACT")
    if m := _HALF.search(text):
        h = int(m.group(1)) if m.group(1) else (1 if m.group(3).lower() == "first" else 2)
        y = int(m.group(2) or m.group(4))
        return _result(text, _iso(y, 6 * h - 5), _iso(y, 6 * h), "half", "EXACT")
    if m := _MONTH_YEAR.search(text):
        mo, y = _month(m.group(1)), int(m.group(2))
        return _result(text, _iso(y, mo), None, "month", "EXACT")
    if m := _ISO_MONTH.search(text):
        y, mo = int(m.group(1)), int(m.group(2))
        if _valid(mo):
            return _result(text, _iso(y, mo), None, "month", "EXACT")
    if m := _DECADE.search(text):
        y = int(m.group(1))
        return _result(text, _iso(y), _iso(y + 9), "decade", "APPROXIMATE")
    if m := _YEAR_ONLY.search(text):
        return _result(text, _iso(int(m.group(1))), None, "year", "EXACT")
    return None


def normalize_date(text: str | None) -> dict[str, Any]:
    """Normalize one date phrase. Never raises; never invents a date."""
    original = (text or "").strip()
    if not original:
        return _result("", None, None, "unknown", "UNKNOWN", note="No date stated.")

    lowered = original.lower()

    # Ranges: "2019-2021", "between May 2020 and June 2021", "Jan 3 to Feb 5, 2024".
    if _RANGE_HINT.search(lowered) or re.search(rf"{_YEAR}\s*[-–—]\s*{_YEAR}", original):
        body = re.sub(r"^\s*(between|from)\s+", "", original, flags=re.I)
        parts: list[str] = []
        for sep in _RANGE_SEPARATORS:
            parts = [p for p in sep.split(body, maxsplit=1) if p and p.strip()]
            if len(parts) == 2:
                break
        if len(parts) == 2:
            left, right = _parse_point(parts[0]), _parse_point(parts[1])
            # "Jan 3 to Feb 5, 2024": borrow the year for the left side.
            if left is None and right is not None and right["start"]:
                left = _parse_point(f"{parts[0]} {right['start'][:4]}")
            if left and right and left["start"] and right["start"]:
                certainty = "APPROXIMATE" if (
                    left["certainty"] != "EXACT" or right["certainty"] != "EXACT"
                    or _APPROX.search(lowered)
                ) else "EXACT"
                start, end = left["start"], right["end"] or right["start"]
                if start > end:
                    start, end = end, start
                return _result(original, start, end, "range", certainty)

    point = _parse_point(original)
    qualifier_match = _QUALIFIER.search(lowered)
    qualifier = qualifier_match.group(1).lower() if qualifier_match else None

    if point is None:
        if _RELATIVE.search(lowered):
            return _result(
                original, None, None, "unknown", "RELATIVE",
                note="Relative date; it cannot be placed without an anchor date.",
            )
        return _result(original, None, None, "unknown", "UNKNOWN",
                       note="No recognisable calendar date.")

    point["text"] = original
    point["qualifier"] = qualifier
    if point["certainty"] == "EXACT" and (_APPROX.search(lowered) or qualifier):
        point["certainty"] = "APPROXIMATE"
    return point


def sort_key(normalized: dict[str, Any]) -> str | None:
    """Chronological key for a normalized date, or None if undated."""
    start = normalized.get("start")
    if not start:
        return None
    # Pad partial dates field by field ("2024" -> "2024-00-00") so a
    # year sorts before its months, which sort before their days.
    parts = (start.split("-") + ["00", "00"])[:3]
    return "-".join(parts)


# Phrases that look like dates inside free text; used by the
# pattern-based fallback extractor when the model is unavailable.
DATE_PHRASE_RE = re.compile(
    "|".join(
        [
            rf"\b(?:between|from)\s+(?:{_MONTH_ALT})?\.?\s*\d{{0,2}},?\s*{_YEAR}\s+(?:and|to|until)\s+(?:{_MONTH_ALT})?\.?\s*\d{{0,2}},?\s*{_YEAR}",
            rf"\b{_YEAR}\s*[-–—]\s*{_YEAR}\b",
            _ISO_DAY.pattern,
            _MDY.pattern,
            _DMY.pattern,
            _NUMERIC.pattern,
            _QUARTER.pattern,
            _QUARTER_WORDS.pattern,
            _HALF.pattern,
            rf"\b(?:early|mid|late)[- ]{_YEAR}\b",
            rf"\b(?:circa|c\.|ca\.)\s*{_YEAR}\b",
            _MONTH_YEAR.pattern,
            _DECADE.pattern,
            rf"\b(?:in|by|since|during|before|after)\s+{_YEAR}\b",
        ]
    ),
    re.I,
)


def find_date_phrases(text: str, limit: int = 20) -> list[str]:
    """Return up to ``limit`` distinct date-like phrases found in ``text``."""
    found: list[str] = []
    for m in DATE_PHRASE_RE.finditer(text or ""):
        phrase = m.group(0).strip()
        if phrase and phrase not in found:
            found.append(phrase)
        if len(found) >= limit:
            break
    return found
