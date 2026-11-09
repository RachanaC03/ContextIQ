"""Governed, graph-based retrieval.

question -> terms/products/periods -> graph walk (drops deprecated) -> per-source permission check
-> per-source time-filtered vector search -> graph-aware re-ranking -> per-source cap -> ContextBundle
"""
from __future__ import annotations

from ..context.graph import ContextGraph
from ..context.store import VectorStore, and_filters
from ..governance.audit import AuditLog
from ..governance.policy import AccessPolicy
from ..metadata import Metadata
from .models import ContextBundle, Evidence
from .temporal import resolve_periods
from .violations import find_violations

PRODUCT_BOOST = 0.15
DIRECT_SOURCE_BOOST = 0.10
PERIOD_BOOST = 0.10


class GovernedRetriever:
    def __init__(self, meta: Metadata, graph: ContextGraph, policy: AccessPolicy, store: VectorStore,
                 audit: AuditLog, as_of: str, per_source_n: int = 6, per_source_cap: int = 3) -> None:
        self.meta, self.graph, self.policy, self.store, self.audit = meta, graph, policy, store, audit
        self.as_of, self.per_source_n, self.per_source_cap = as_of, per_source_n, per_source_cap

    def retrieve(self, question: str, role: str, top_k: int = 8) -> ContextBundle:
        self.policy.require_role(role)
        periods = resolve_periods(question, self.as_of)
        plan = self.graph.plan(question)
        bundle = ContextBundle(question=question, role=role, mode="graph", periods=periods,
                               products=plan.products, terms=plan.terms,
                               dropped_deprecated=plan.dropped)

        for d in plan.dropped:
            self.audit.record(role, "retrieve_" + d["kind"], d["id"], "deny", d["reason"])

        # ---- definitions and readable schemas (table-level and column-level permissions)
        for term_id in plan.terms:
            table = self.meta.terms[term_id].defines
            table = table if table in plan.defining_tables else self.meta.tables[table].superseded_by
            if table and table in plan.defining_tables:
                bundle.definitions.append({"term": term_id, "table": table,
                                           "definition": self.meta.terms[term_id].definition})
        for t in plan.tables:
            cols = self.policy.table_columns(role, t)
            if cols is None:
                bundle.withheld.append({"kind": "table", "id": t, "reason": "table not permitted"})
                self.audit.record(role, "retrieve_table", t, "deny", "table not permitted")
                continue
            tbl = self.meta.tables[t]
            bundle.schemas[t] = [{"name": c, "type": tbl.columns[c].type,
                                  "description": tbl.columns[c].description} for c in cols]
            self.audit.record(role, "retrieve_table", t, "allow", "table permitted")
        bundle.definitions = [d for d in bundle.definitions if d["table"] in bundle.schemas]
        bundle.lineage = self._visible_lineage(plan.tables, set(bundle.schemas))

        # ---- per-source permission check, search and re-ranking
        time_filter = None
        if periods:
            time_filter = {"$or": [{"month": {"$in": periods}}, {"month": "all"}]}
        candidates: list[Evidence] = []
        for source_id in plan.doc_sources:
            allowed, reason = self.policy.can_read_source(role, source_id)
            self.audit.record(role, "retrieve_source", source_id, "allow" if allowed else "deny", reason)
            if not allowed:
                bundle.withheld.append({"kind": "source", "id": source_id, "reason": reason})
                continue
            hits = self.store.query(question, n=self.per_source_n,
                                    where=and_filters({"source_id": source_id}, time_filter))
            scored = []
            for h in hits:
                m = h.metadata
                boosts: dict[str, float] = {}
                if plan.products and any(f"|{p}|" in m["product_ids"] for p in plan.products):
                    boosts["product"] = PRODUCT_BOOST
                if source_id in plan.direct_sources:
                    boosts["direct_source"] = DIRECT_SOURCE_BOOST
                if periods and m["month"] in periods:
                    boosts["period"] = PERIOD_BOOST
                scored.append(Evidence(h.chunk_id, m["doc_id"], m["title"], source_id, m["tier"], m["month"],
                                       round(h.similarity + sum(boosts.values()), 4), h.similarity,
                                       h.text, boosts))
            scored.sort(key=lambda e: -e.score)
            candidates.extend(scored[: self.per_source_cap])   # per-source cap

        candidates.sort(key=lambda e: -e.score)
        bundle.evidence = candidates[:top_k]
        bundle.violations = find_violations(bundle.evidence, role, self.meta, self.policy)
        return bundle

    def _visible_lineage(self, tables: list[str], readable: set[str]) -> list[str]:
        """Lineage text that never names a table the role cannot read (hidden ones are only counted)."""
        lines = []
        for t in tables:
            if t not in readable:
                continue
            ups = [e["upstream"] for e in self.meta.lineage
                   if e["downstream"] == t and not self.meta.tables[e["upstream"]].deprecated]
            if not ups:
                continue
            visible = [u for u in ups if u in readable]
            hidden = len(ups) - len(visible)
            line = f"{t} is fed by: " + (", ".join(visible) if visible else "(restricted)")
            if hidden and visible:
                line += f" (+{hidden} upstream table(s) restricted for this role)"
            lines.append(line)
        return lines
