import pytest

from contextiq.context.graph import ContextGraph


@pytest.fixture
def graph(meta):
    return ContextGraph(meta)


def test_matches_business_term(graph):
    assert "customer_complaints" in graph.match_terms("Why did customer complaints increase?")


def test_matching_respects_word_boundaries(graph):
    assert graph.match_terms("sales") == ["revenue"]
    assert graph.match_terms("the disorders of nature") == []


def test_matches_products_by_id_name_and_alias(graph):
    assert graph.match_products("what about P-107?") == ["P-107"]
    assert graph.match_products("the AeroBrew coffee maker") == ["P-104"]
    assert graph.match_products("nothing relevant") == []


def test_term_defines_authoritative_table(graph):
    assert graph.plan("customer complaints last month").defining_tables == ["complaints_monthly"]


def test_lineage_walk_reaches_upstream_tables(graph):
    plan = graph.plan("customer complaints")
    assert {"complaints", "orders", "production_batches"} <= set(plan.tables)


def test_upstream_is_ordered_nearest_first(graph):
    assert graph.upstream("complaints_monthly")[:2] == ["complaints", "orders"]


def test_linked_documents_are_found(graph):
    plan = graph.plan("customer complaints")
    assert {"support_digests", "quality_reports", "finance_reports"} <= set(plan.doc_sources)
    assert {"support_digests", "finance_reports"} == plan.direct_sources


def test_deprecated_table_is_dropped_and_replaced_by_successor(graph):
    plan = graph.plan("show the legacy complaint stats")
    assert plan.defining_tables == ["complaints_monthly"]
    assert any(d["id"] == "legacy_complaint_stats" and "superseded" in d["reason"] for d in plan.dropped)
    assert "legacy_stats_notes" not in plan.doc_sources


def test_unmatched_question_falls_back_to_all_live_sources(graph, meta):
    plan = graph.plan("tell me something interesting")
    assert plan.fallback
    assert "legacy_stats_notes" not in plan.doc_sources
    assert set(plan.doc_sources) == {s for s, v in meta.doc_sources.items() if not v.deprecated}
    assert any(d["id"] == "legacy_stats_notes" for d in plan.dropped)


def test_lineage_text_is_readable(graph):
    assert "complaints_monthly is fed by: complaints, orders" in graph.plan("customer complaints").lineage
