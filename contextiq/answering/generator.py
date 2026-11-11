
"""Create evidence-grounded reports from ContextIQ retrieval results."""

from __future__ import annotations

from typing import Any

from ..retrieval.models import ContextBundle


def generate_answer(bundle: ContextBundle) -> dict[str, Any]:
    """Build a structured report using only the permitted retrieved evidence."""

    findings = []

    for index, evidence in enumerate(bundle.evidence, start=1):
        findings.append({
            "citation": f"[{index}]",
            "title": evidence.title,
            "source_id": evidence.source_id,
            "document_id": evidence.doc_id,
            "period": evidence.month,
            "text": evidence.text,
        })

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
        "limitations": limitations,
        "access_notice": bundle.access_notice,
    }
