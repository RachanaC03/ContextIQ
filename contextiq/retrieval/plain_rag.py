"""Baseline: plain vector search over the whole index. Ignores roles, lineage and deprecation.
It shares the same index as the governed retriever, so any difference is due to governance."""
from __future__ import annotations

from ..context.store import VectorStore
from ..governance.policy import AccessPolicy
from ..metadata import Metadata
from .models import ContextBundle, Evidence
from .violations import find_violations


class PlainRetriever:
    def __init__(self, meta: Metadata, policy: AccessPolicy, store: VectorStore) -> None:
        self.meta, self.policy, self.store = meta, policy, store

    def retrieve(self, question: str, role: str, top_k: int = 8) -> ContextBundle:
        self.policy.require_role(role)
        evidence = []
        for h in self.store.query(question, n=top_k):
            m = h.metadata
            evidence.append(Evidence(h.chunk_id, m["doc_id"], m["title"], m["source_id"], m["tier"],
                                     m["month"], h.similarity, h.similarity, h.text))
        bundle = ContextBundle(question=question, role=role, mode="plain", evidence=evidence)
        bundle.violations = find_violations(evidence, role, self.meta, self.policy)
        return bundle
