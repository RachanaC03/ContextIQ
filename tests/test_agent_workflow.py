
from types import SimpleNamespace

from contextiq.agents.workflow import build_answer_graph
from contextiq.retrieval.models import ContextBundle, Evidence


class FakeEngine:
    def __init__(self, bundle):
        self.bundle = bundle

    def ask(self, question, role, plain=False, top_k=8):
        assert plain is False
        return self.bundle


def make_evidence():
    return Evidence(
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


def make_bundle():
    return ContextBundle(
        question="What happened to P-104 complaints?",
        role="support_analyst",
        mode="graph",
        periods=["2026-10"],
        products=["P-104"],
        evidence=[make_evidence()],
    )


def test_workflow_generates_answer_with_valid_citation():
    bundle = make_bundle()
    engine = FakeEngine(bundle)

    def fake_chat(**kwargs):
        return SimpleNamespace(
            message=SimpleNamespace(
                content="P-104 complaints increased in October [1]."
            )
        )

    graph = build_answer_graph(engine, chat_fn=fake_chat)

    result = graph.invoke({
        "question": bundle.question,
        "role": bundle.role,
        "top_k": 8,
        "model": "test-model",
    })

    assert "[1]" in result["answer"]
    assert result["citation_status"] == "valid"
    assert len(result["bundle"].evidence) == 1


def test_workflow_does_not_call_llm_without_evidence():
    bundle = ContextBundle(
        question="What caused the increase?",
        role="support_analyst",
        mode="graph",
    )
    engine = FakeEngine(bundle)

    def unexpected_chat(**kwargs):
        raise AssertionError("LLM should not be called without evidence")

    graph = build_answer_graph(engine, chat_fn=unexpected_chat)

    result = graph.invoke({
        "question": bundle.question,
        "role": bundle.role,
    })

    assert result["citation_status"] == "not_applicable"
    assert "could not find permitted evidence" in result["answer"]


def test_workflow_adds_fallback_citation_when_model_omits_it():
    bundle = make_bundle()
    engine = FakeEngine(bundle)

    def no_citation_chat(**kwargs):
        return SimpleNamespace(
            message=SimpleNamespace(
                content="P-104 complaints increased in October."
            )
        )

    graph = build_answer_graph(engine, chat_fn=no_citation_chat)

    result = graph.invoke({
        "question": bundle.question,
        "role": bundle.role,
        "top_k": 8,
        "model": "test-model",
    })

    assert "[1]" in result["answer"]
    assert result["citation_status"] == "fallback_citations_added"
