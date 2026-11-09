import pytest

from contextiq.governance.policy import AccessPolicy, UnknownRoleError
from contextiq.governance.sql_guard import SQLGuard


@pytest.fixture
def guard(meta):
    return SQLGuard(meta, AccessPolicy(meta))


def allowed(guard, sql, role="support_analyst"):
    return guard.check(sql, role)


def test_allows_simple_select(guard):
    r = allowed(guard, "SELECT product_id, complaint_rate_pct FROM complaints_monthly WHERE month='2026-10' ORDER BY 2 DESC")
    assert r.allowed and r.tables == ["complaints_monthly"]


def test_allows_join_with_aliases(guard):
    assert allowed(guard, "SELECT o.order_id, c.category FROM orders o JOIN complaints c ON c.order_id = o.order_id").allowed


def test_allows_aggregates_and_group_by(guard):
    assert allowed(guard, "SELECT product_id, SUM(complaints) AS n FROM complaints_monthly GROUP BY product_id ORDER BY n DESC").allowed


def test_allows_count_star_even_with_restricted_columns(guard):
    assert allowed(guard, "SELECT COUNT(*) FROM orders").allowed


def test_allows_cte(guard):
    assert allowed(guard, "WITH t AS (SELECT product_id, complaints FROM complaints_monthly) SELECT product_id FROM t").allowed


def test_allows_star_when_no_columns_restricted(guard):
    assert allowed(guard, "SELECT * FROM complaints_monthly").allowed


@pytest.mark.parametrize("sql", [
    "INSERT INTO orders VALUES (1)",
    "UPDATE orders SET quantity = 1",
    "DELETE FROM orders",
    "DROP TABLE orders",
    "CREATE TABLE x (a INT)",
    "PRAGMA table_info(orders)",
    "ATTACH DATABASE 'x.db' AS x",
])
def test_denies_non_select(guard, sql):
    r = allowed(guard, sql, "executive")
    assert not r.allowed


def test_denies_multiple_statements(guard):
    r = allowed(guard, "SELECT product_id FROM products; DROP TABLE orders", "executive")
    assert not r.allowed and "one statement" in r.reason


def test_denies_union(guard):
    assert not allowed(guard, "SELECT product_id FROM products UNION SELECT product_id FROM orders", "executive").allowed


def test_denies_unknown_table(guard):
    r = allowed(guard, "SELECT * FROM sqlite_master", "executive")
    assert not r.allowed and "not in the catalog" in r.reason


def test_denies_deprecated_table_and_suggests_replacement(guard):
    r = allowed(guard, "SELECT * FROM legacy_complaint_stats", "executive")
    assert not r.allowed and "deprecated" in r.reason and "complaints_monthly" in r.reason


def test_denies_table_not_permitted_for_role(guard):
    r = allowed(guard, "SELECT * FROM revenue_monthly")
    assert not r.allowed and "may not read table" in r.reason


def test_column_level_denial(guard):
    r = allowed(guard, "SELECT unit_price FROM orders")
    assert not r.allowed and "unit_price" in r.reason


def test_column_level_allowed_for_finance(guard):
    assert allowed(guard, "SELECT unit_price FROM orders", "finance_manager").allowed


def test_denies_restricted_column_in_where_clause(guard):
    assert not allowed(guard, "SELECT order_id FROM orders WHERE unit_price > 50").allowed


def test_denies_restricted_column_in_order_by(guard):
    assert not allowed(guard, "SELECT order_id FROM orders ORDER BY unit_price").allowed


def test_denies_restricted_qualified_column(guard):
    assert not allowed(guard, "SELECT o.unit_price FROM orders o").allowed


def test_denies_restricted_column_inside_subquery(guard):
    assert not allowed(guard, "SELECT order_id FROM orders WHERE order_id IN (SELECT order_id FROM orders WHERE unit_price > 10)").allowed


def test_denies_star_on_table_with_restricted_columns(guard):
    r = allowed(guard, "SELECT * FROM orders")
    assert not r.allowed and "unit_price" in r.reason


def test_denies_qualified_star_on_restricted_table(guard):
    assert not allowed(guard, "SELECT o.* FROM orders o").allowed


def test_denies_table_valued_function(guard):
    assert not allowed(guard, "SELECT * FROM pragma_table_info('orders')", "executive").allowed


def test_denies_unknown_column(guard):
    r = allowed(guard, "SELECT nonsense FROM orders")
    assert not r.allowed and "unknown column" in r.reason


def test_denies_garbage(guard):
    assert not allowed(guard, "this is not sql at all").allowed


def test_unknown_role_raises(guard):
    with pytest.raises(UnknownRoleError):
        guard.check("SELECT 1", "intern")
