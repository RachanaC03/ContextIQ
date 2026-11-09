import pytest

from contextiq.governance.policy import AccessDenied

Q_OK = "SELECT product_id, complaint_rate_pct FROM complaints_monthly WHERE month='2026-10' ORDER BY 2 DESC"


def test_runs_allowed_query(env):
    res = env.sql(Q_OK, "support_analyst")
    assert res.columns == ["product_id", "complaint_rate_pct"]
    assert res.rows[0][0] == "P-104" and res.rows[1][0] == "P-107"


def test_denied_query_raises_and_is_audited(env):
    before = env.audit.count(decision="deny", action="sql")
    with pytest.raises(AccessDenied, match="unit_price"):
        env.sql("SELECT unit_price FROM orders", "support_analyst")
    assert env.audit.count(decision="deny", action="sql") == before + 1


def test_allowed_query_is_audited(env):
    before = env.audit.count(decision="allow", action="sql")
    env.sql(Q_OK, "support_analyst")
    assert env.audit.count(decision="allow", action="sql") == before + 1


def test_row_cap_truncates(env):
    res = env.sql("SELECT order_id FROM orders", "support_analyst", max_rows=10)
    assert len(res.rows) == 10 and res.truncated


def test_authorizer_blocks_restricted_column_even_if_guard_bypassed(env):
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        env.sql_executor._execute("SELECT unit_price FROM orders", "support_analyst", 5)


def test_authorizer_blocks_other_tables_even_if_guard_bypassed(env):
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        env.sql_executor._execute("SELECT * FROM revenue_monthly", "support_analyst", 5)


def test_connection_is_read_only(env):
    import sqlite3
    conn = sqlite3.connect(f"file:{env.settings.db_path}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM orders")
    conn.close()
