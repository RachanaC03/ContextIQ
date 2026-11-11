
from contextiq.answering.generator import generate_answer
from contextiq.retrieval.models import ContextBundle, Evidence


def test_generate_answer_with_evidence():
    evidence = Evidence(
        chunk_id="chunk-1",
        doc_id="doc-1",
        title="October Complaint Report",
        source_id="complaints",
        tier="support",
        month="2026-10",
        score=0.95,
        vector_score=0.90,
        text="P-104 complaints increased during October.",
    )

    bundle = ContextBundle(
        question="Why did complaints increase?",
        role="support_analyst",
        mode="governed",
        periods=["2026-10"],
        products=["P-104"],
        evidence=[evidence],
    )

    result = generate_answer(bundle)

    assert result["status"] == "evidence_found"
    assert result["question"] == "Why did complaints increase?"
    assert len(result["findings"]) == 1
    assert result["findings"][0]["citation"] == "[1]"
    assert result["findings"][0]["text"] == (
        "P-104 complaints increased during October."
    )
    assert result["resolved_context"]["products"] == ["P-104"]

    assert len(result["key_observations"]) == 1
    assert result["key_observations"][0]["citation"] == "[1]"
    assert result["key_observations"][0]["text"] == (
        "P-104 complaints increased during October."
    )
    assert result["affected_products"] == [
        {"product": "P-104", "citations": ["[1]"]}
    ]


def test_generate_answer_without_evidence():
    bundle = ContextBundle(
        question="What caused the increase?",
        role="support_analyst",
        mode="governed",
    )

    result = generate_answer(bundle)

    assert result["status"] == "no_evidence"
    assert result["findings"] == []
    assert "cannot be produced" in result["summary"]
    assert len(result["limitations"]) == 3
    assert result["key_observations"] == []
    assert result["affected_products"] == []
