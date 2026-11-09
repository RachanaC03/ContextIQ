import pytest

from contextiq.governance.audit import AuditLog


def test_record_and_read_back(tmp_path):
    log = AuditLog(tmp_path / "a.db")
    log.record("support_analyst", "sql", "SELECT 1", "allow", "ok", {"rows": 1})
    log.record("finance_manager", "retrieve_source", "support_digests", "deny", "tier not permitted")
    rows = log.recent()
    assert [r["decision"] for r in rows] == ["deny", "allow"]   # newest first
    assert rows[0]["resource"] == "support_digests"


def test_filters_and_counts(tmp_path):
    log = AuditLog(tmp_path / "a.db")
    for d in ("allow", "allow", "deny"):
        log.record("r", "sql", "x", d)
    assert log.count() == 3 and log.count(decision="deny") == 1 and log.count(action="sql") == 3
    assert len(log.recent(decision="allow")) == 2 and log.recent(role="nobody") == []


def test_persists_across_instances(tmp_path):
    AuditLog(tmp_path / "a.db").record("r", "sql", "x", "allow")
    assert AuditLog(tmp_path / "a.db").count() == 1


def test_rejects_invalid_decision(tmp_path):
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        AuditLog(tmp_path / "a.db").record("r", "sql", "x", "maybe")
