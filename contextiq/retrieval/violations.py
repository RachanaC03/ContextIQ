"""Detect evidence the role should not have received."""
from __future__ import annotations

from ..governance.policy import AccessPolicy
from ..metadata import Metadata
from .models import Evidence


def find_violations(evidence: list[Evidence], role: str, meta: Metadata, policy: AccessPolicy) -> list[dict]:
    found = []
    for e in evidence:
        allowed, _ = policy.can_read_source(role, e.source_id)
        if not allowed:
            found.append({"chunk_id": e.chunk_id, "doc_id": e.doc_id, "source_id": e.source_id,
                          "reason": f"tier '{e.tier}' is not permitted for role '{role}'"})
        if meta.doc_sources[e.source_id].deprecated:
            found.append({"chunk_id": e.chunk_id, "doc_id": e.doc_id, "source_id": e.source_id,
                          "reason": "deprecated source"})
    return found
