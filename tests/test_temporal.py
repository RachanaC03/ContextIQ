import pytest

from contextiq.retrieval.temporal import resolve_periods

AS_OF = "2026-11-15"


@pytest.mark.parametrize("question,expected", [
    ("why did complaints rise last month", ["2026-10"]),
    ("how are orders doing this month", ["2026-11"]),
    ("complaints in 2026-03", ["2026-03"]),
    ("what happened in March", ["2026-03"]),
    ("revenue in September 2025", ["2025-09"]),
    ("results for the last quarter", ["2026-07", "2026-08", "2026-09"]),
    ("results for this quarter", ["2026-10", "2026-11", "2026-12"]),
    ("trend over the last 3 months", ["2026-08", "2026-09", "2026-10"]),
    ("trend over the past two months", ["2026-09", "2026-10"]),
    ("what is a complaint", []),
    ("this may be a problem", []),
    ("sales in May", ["2026-05"]),
    ("compare October and September", ["2026-09", "2026-10"]),
])
def test_resolve_periods(question, expected):
    assert resolve_periods(question, AS_OF) == expected


def test_year_rollover():
    assert resolve_periods("complaints last month", "2027-01-10") == ["2026-12"]
    assert resolve_periods("what happened in December", "2027-01-10") == ["2026-12"]
