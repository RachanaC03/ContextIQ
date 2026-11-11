
"""Create evidence-grounded reports from ContextIQ retrieval results."""

from __future__ import annotations

from typing import Any

from ..retrieval.models import ContextBundle


def generate_answer(bundle: ContextBundle) -> dict[str, Any]:
    """Build a structured report using only permitted retrieved evidence."""

    findings = []
    key_observations = []
    product_citations: dict[str, list[str]] = {}

    for index, evidence in enumerate(bundle.evidence, start=1):
        citation = f"[{index}]"

        findings.append({
            "citation": citation,
            "title": evidence.title,
            "source_id": evidence.source_id,
            "document_id": evidence.doc_id,
            "period": evidence.month,
            "text": evidence.text,
        })

        key_observations.append({
            "citation": citation,
            "text": evidence.text,
        })

        evidence_text = evidence.text.casefold()

        for product in bundle.products:
            if product.casefold() in evidence_text:
                citations = product_citations.setdefault(product, [])
                if citation not in citations:
                    citations.append(citation)

    affected_products = [
        {
            "product": product,
            "citations": citations,
        }
        for product, citations in product_citations.items()
    ]

    if findings:
        status = "evidence_found"
        summary = (
            f"Retrieved {len(findings)} evidence item(s) "
            f"for the question using the {bundle.role} role."
        )
    else:
        status = "no_evidence"
        summary = (
            "No permitted evidence was found for this question. "
            "A reliable answer cannot be produced from the available evidence."
        )

    limitations = [
        "This report organizes retrieved evidence; it does not independently "
        "verify claims or establish cause and effect.",
        "Any conclusion or recommendation should be checked against the "
        "underlying evidence."
    ]

    if not findings:
        limitations.append(
            "More relevant, permitted information may be needed to answer "
            "the question."
        )

    return {
        "question": bundle.question,
        "role": bundle.role,
        "status": status,
        "summary": summary,
        "resolved_context": {
            "periods": bundle.periods,
            "products": bundle.products,
            "business_terms": bundle.terms,
        },
        "findings": findings,
        "key_observations": key_observations,
        "affected_products": affected_products,
        "limitations": limitations,
        "access_notice": bundle.access_notice,
    }
