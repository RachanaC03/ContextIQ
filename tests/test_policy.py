import pytest

from contextiq.governance.policy import AccessPolicy, UnknownRoleError


@pytest.fixture
def policy(meta):
    return AccessPolicy(meta)


def test_roles_listed(policy):
    assert {"support_analyst", "quality_engineer", "finance_manager", "executive"} <= set(policy.roles())


def test_unknown_role_raises(policy):
    with pytest.raises(UnknownRoleError):
        policy.tiers("intern")


def test_support_reads_support_but_not_quality_or_finance(policy):
    assert policy.can_read_source("support_analyst", "support_digests")[0]
    assert not policy.can_read_source("support_analyst", "quality_reports")[0]
    assert not policy.can_read_source("support_analyst", "finance_reports")[0]


def test_finance_cannot_read_support_or_quality(policy):
    assert not policy.can_read_source("finance_manager", "support_tickets")[0]
    assert not policy.can_read_source("finance_manager", "quality_reports")[0]
    assert policy.can_read_source("finance_manager", "finance_reports")[0]


def test_everyone_reads_general(policy):
    assert all(policy.can_read_source(r, "product_faq")[0] for r in policy.roles())


def test_executive_reads_all_tiers(policy, meta):
    assert all(policy.can_read_source("executive", s)[0] for s in meta.doc_sources)


def test_unknown_source_denied(policy):
    assert policy.can_read_source("executive", "nope") == (False, "unknown source")


def test_support_cannot_see_unit_price(policy):
    assert "unit_price" not in policy.table_columns("support_analyst", "orders")
    assert "order_id" in policy.table_columns("support_analyst", "orders")


def test_finance_sees_unit_price(policy):
    assert "unit_price" in policy.table_columns("finance_manager", "orders")


def test_table_level_denial(policy):
    assert policy.table_columns("support_analyst", "revenue_monthly") is None
    assert not policy.can_read_table("finance_manager", "production_batches")
    assert policy.can_read_table("quality_engineer", "production_batches")


def test_executive_gets_every_column(policy, meta):
    assert set(policy.table_columns("executive", "orders")) == set(meta.tables["orders"].columns)
