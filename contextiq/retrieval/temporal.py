"""Resolve relative and explicit time expressions in a question into YYYY-MM months."""
from __future__ import annotations

import re

_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
           "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
           "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
           "sept": 9, "oct": 10, "nov": 11, "dec": 12}
_NUMWORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "twelve": 12}


def _shift(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def _fmt(y: int, m: int) -> str:
    return f"{y}-{m:02d}"


def resolve_periods(question: str, as_of: str) -> list[str]:
    """Return sorted YYYY-MM months mentioned in `question`, relative to the date `as_of`."""
    q = question.lower()
    ay, am = int(as_of[:4]), int(as_of[5:7])
    out: set[str] = set()

    for y, m in re.findall(r"\b(20\d\d)-(0[1-9]|1[0-2])\b", q):
        out.add(_fmt(int(y), int(m)))

    if re.search(r"\blast month\b", q):
        out.add(_fmt(*_shift(ay, am, -1)))
    if re.search(r"\b(this|current) month\b", q):
        out.add(_fmt(ay, am))

    for n in re.findall(r"\b(?:last|past|previous) (\d+|two|three|four|five|six|twelve) months\b", q):
        count = int(n) if n.isdigit() else _NUMWORDS[n]
        out.update(_fmt(*_shift(ay, am, -i)) for i in range(1, count + 1))

    quarter_start = 3 * ((am - 1) // 3) + 1
    if re.search(r"\blast quarter\b", q):
        sy, sm = _shift(ay, quarter_start, -3)
        out.update(_fmt(*_shift(sy, sm, i)) for i in range(3))
    if re.search(r"\bthis quarter\b", q):
        out.update(_fmt(*_shift(ay, quarter_start, i)) for i in range(3))

    names = "|".join(sorted(_MONTHS, key=len, reverse=True))
    for name, year in re.findall(rf"\b({names})\b(?:\s+(20\d\d))?", q):
        if name == "may" and not re.search(r"\b(in|during|for|of|since) may\b|\bmay 20\d\d\b", q):
            continue  # "may" is usually a verb
        m = _MONTHS[name]
        if year:
            y = int(year)
        else:  # most recent occurrence not after as_of
            y = ay if m <= am else ay - 1
        out.add(_fmt(y, m))
    return sorted(out)
