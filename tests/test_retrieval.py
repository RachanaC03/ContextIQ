import re
from collections import Counter

import pytest

from contextiq.context.ingest import chunk_text


def sources(bundle):
    return {e.source_id for e in bundle.evidence}


def test_support_analyst_gets_only_permitted_tiers(env, question):
    b = env.ask(question, "support_analyst")
    assert b.evidence and {e.tier for e in b.evidence} <= {"general", "support"}


def test_finance_manager_gets_only_permitted_tiers(env, question):
    b = env.ask(question, "finance_manager")
    assert b.evidence and {e.tier for e in b.evidence} <= {"general", "finance"}


@pytest.mark.parametrize("role", ["support_analyst", "quality_engineer", "finance_manager", "executive"])
def test_governed_retrieval_has_zero_violations(env, question, role):
    assert env.ask(question, role).violations == []


def test_same_question_different_roles_get_different_evidence(env, question):
    a = {e.doc_id for e in env.ask(question, "support_analyst").evidence}
    f = {e.doc_id for e in env.ask(question, "finance_manager").evidence}
    assert a != f


def test_plain_baseline_leaks_to_finance_manager(env, question):
    b = env.ask(question, "finance_manager", plain=True)
    assert len(b.violations) > 0
    assert any("support" in v["reason"] or "quality" in v["reason"] for v in b.violations)


def test_withheld_sources_are_counted_not_described(env, question):
    b = env.ask(question, "finance_manager")
    assert len(b.withheld) >= 3
    prompt = b.to_prompt()
    assert f"{len(b.withheld)} source(s)" in prompt
    for w in b.withheld:
        if w["kind"] == "source":              # source ids never appear in the model-facing context
            assert w["id"] not in prompt
        else:                                  # withheld tables are not exposed in schemas or lineage
            assert w["id"] not in b.schemas
            assert w["id"] not in re.findall(r"[a-z_]+", " ".join(b.lineage))
    withheld_titles = {d.title for d in env.plain.retrieve(question, "executive", 20).evidence
                       if d.tier in ("support", "quality")}
    assert withheld_titles and not any(t in prompt for t in withheld_titles)


def test_lineage_hides_restricted_upstream_tables(env, question):
    support = " ".join(env.ask(question, "support_analyst").lineage)
    assert "production_batches" not in support and "restricted" in support
    assert "production_batches" in " ".join(env.ask(question, "quality_engineer").lineage)


def test_deprecated_source_never_retrieved(env):
    b = env.ask("show me the legacy complaint stats", "executive")
    assert "legacy_stats_notes" not in sources(b)
    assert any(d["id"] == "legacy_complaint_stats" for d in b.dropped_deprecated)
    assert b.definitions and b.definitions[0]["table"] == "complaints_monthly"


def test_plain_baseline_can_retrieve_deprecated_decoy(env):
    b = env.ask("legacy complaint statistics methodology", "executive", plain=True)
    assert "legacy_stats_notes" in sources(b)
    assert any(v["reason"] == "deprecated source" for v in b.violations)


def test_time_filter_limits_evidence_to_last_month(env, question):
    b = env.ask(question, "support_analyst")
    assert b.periods == ["2026-10"]
    assert {e.month for e in b.evidence} <= {"2026-10", "all"}


def test_per_source_cap_is_respected(env, question):
    counts = Counter(e.source_id for e in env.ask(question, "executive", top_k=20).evidence)
    assert max(counts.values()) <= env.governed.per_source_cap


def test_quality_engineer_sees_incident_report(env, question):
    ids = {e.doc_id for e in env.ask(question, "quality_engineer").evidence}
    assert "quality_reports-incident-2026-10" in ids


def test_support_analyst_never_sees_incident_report(env, question):
    ids = {e.doc_id for e in env.ask(question, "support_analyst").evidence}
    assert "quality_reports-incident-2026-10" not in ids


def test_product_in_question_boosts_matching_documents(env):
    import json
    docs = [json.loads(l) for l in env.settings.documents_path.read_text().splitlines()]
    about_p104 = {d["doc_id"] for d in docs if "P-104" in d["product_ids"]}
    b = env.ask("what went wrong with AeroBrew Pro last month", "quality_engineer")
    assert b.products == ["P-104"]
    boosted = [e for e in b.evidence if "product" in e.boosts]
    assert boosted and all(e.doc_id in about_p104 for e in boosted)
    assert all(e.doc_id not in about_p104 for e in b.evidence if "product" not in e.boosts)


def test_schemas_exclude_restricted_columns(env, question):
    b = env.ask(question, "support_analyst")
    assert "unit_price" not in {c["name"] for c in b.schemas["orders"]}
    assert "unit_price" in {c["name"] for c in env.ask(question, "finance_manager").schemas["orders"]}


def test_inaccessible_tables_are_not_exposed(env, question):
    b = env.ask(question, "finance_manager")
    assert "complaints" not in b.schemas and "production_batches" not in b.schemas


def test_prompt_contains_definitions_lineage_and_notice(env, question):
    prompt = env.ask(question, "support_analyst").to_prompt()
    for part in ("## Definitions", "complaints_monthly", "## Lineage", "## Evidence", "## Access notice"):
        assert part in prompt


def test_question_without_known_terms_still_returns_evidence(env):
    b = env.ask("what is the warranty period", "support_analyst")
    assert b.evidence and not b.violations


def test_retrieval_decisions_are_audited(env, question):
    allow, deny = env.audit.count("allow", "retrieve_source"), env.audit.count("deny", "retrieve_source")
    env.ask(question, "finance_manager")
    assert env.audit.count("allow", "retrieve_source") > allow
    assert env.audit.count("deny", "retrieve_source") > deny


def test_index_has_chunks_for_every_document(env):
    assert env.store.count() >= 57


def test_chunking_respects_size_and_keeps_text():
    text = "First paragraph. " * 30 + "\n\n" + "Second paragraph. " * 30
    chunks = chunk_text(text, max_chars=300)
    assert len(chunks) > 2 and all(len(c) <= 300 for c in chunks)
    assert "Second paragraph." in " ".join(chunks)
