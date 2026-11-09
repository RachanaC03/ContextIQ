"""The context graph: business terms -> authoritative tables -> lineage -> linked documents.

Edges (networkx DiGraph):
  term:X   --defines-->       table:T
  table:T  --fed_by-->        table:U      (U is upstream of T)
  table:T  --documented_by--> source:S     (document collection linked to T)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import networkx as nx

from ..metadata import Metadata


@dataclass
class GraphPlan:
    terms: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    defining_tables: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)          # defining + upstream, non-deprecated
    doc_sources: list[str] = field(default_factory=list)     # candidate document sources, non-deprecated
    direct_sources: set[str] = field(default_factory=set)    # sources linked to a defining table
    dropped: list[dict] = field(default_factory=list)        # deprecated items removed before search
    lineage: list[str] = field(default_factory=list)
    fallback: bool = False                                   # no term matched: all live sources considered


def _phrase_regex(phrase: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase.lower()) + r"(?![a-z0-9])")


class ContextGraph:
    def __init__(self, meta: Metadata) -> None:
        self.meta = meta
        g = nx.DiGraph()
        for t in meta.tables.values():
            g.add_node(f"table:{t.name}", kind="table", deprecated=t.deprecated)
        for term in meta.terms.values():
            g.add_node(f"term:{term.id}", kind="term")
            g.add_edge(f"term:{term.id}", f"table:{term.defines}", relation="defines")
        for e in meta.lineage:
            g.add_edge(f"table:{e['downstream']}", f"table:{e['upstream']}", relation="fed_by",
                       note=e.get("note", ""))
        for s in meta.doc_sources.values():
            g.add_node(f"source:{s.id}", kind="source", deprecated=s.deprecated, tier=s.tier)
            for t in s.linked_tables:
                g.add_edge(f"table:{t}", f"source:{s.id}", relation="documented_by")
        self.g = g
        self._lineage = nx.DiGraph(
            (u, v, d) for u, v, d in g.edges(data=True) if d["relation"] == "fed_by")
        self._lineage.add_nodes_from(n for n, d in g.nodes(data=True) if d["kind"] == "table")
        self._term_patterns = sorted(
            ((term.id, _phrase_regex(s)) for term in meta.terms.values() for s in term.synonyms),
            key=lambda x: -len(x[1].pattern))
        self._product_patterns = [
            (p.id, _phrase_regex(x)) for p in meta.products.values()
            for x in (p.id, p.name, *p.aliases)]

    # -------- matching
    def match_terms(self, question: str) -> list[str]:
        q = question.lower()
        found: list[str] = []
        for term_id, pat in self._term_patterns:
            if term_id not in found and pat.search(q):
                found.append(term_id)
        return found

    def match_products(self, question: str) -> list[str]:
        q = question.lower()
        found: list[str] = []
        for pid, pat in self._product_patterns:
            if pid not in found and pat.search(q):
                found.append(pid)
        return found

    # -------- graph queries
    def upstream(self, table: str) -> list[str]:
        """All tables that feed `table`, nearest first."""
        seen = [n for n in nx.bfs_tree(self._lineage, f"table:{table}")][1:]
        return [n.split(":", 1)[1] for n in seen]

    def doc_sources_for_table(self, table: str) -> list[str]:
        return [v.split(":", 1)[1] for _, v, d in self.g.out_edges(f"table:{table}", data=True)
                if d["relation"] == "documented_by"]

    def plan(self, question: str) -> GraphPlan:
        meta = self.meta
        plan = GraphPlan(terms=self.match_terms(question), products=self.match_products(question))

        def drop(kind: str, ident: str, reason: str) -> None:
            if not any(d["id"] == ident and d["kind"] == kind for d in plan.dropped):
                plan.dropped.append({"kind": kind, "id": ident, "reason": reason})

        for term_id in plan.terms:
            table = meta.terms[term_id].defines
            if meta.tables[table].deprecated:
                succ = meta.tables[table].superseded_by
                drop("table", table, f"deprecated; superseded by {succ}" if succ else "deprecated")
                if not succ or meta.tables[succ].deprecated:
                    continue
                table = succ
            if table not in plan.defining_tables:
                plan.defining_tables.append(table)

        plan.tables = list(plan.defining_tables)
        for d in plan.defining_tables:
            for up in self.upstream(d):
                if meta.tables[up].deprecated:
                    drop("table", up, "deprecated")
                elif up not in plan.tables:
                    plan.tables.append(up)

        if plan.tables:
            for t in plan.tables:
                for s in self.doc_sources_for_table(t):
                    if meta.doc_sources[s].deprecated:
                        drop("source", s, "deprecated")
                    elif s not in plan.doc_sources:
                        plan.doc_sources.append(s)
            for d in plan.defining_tables:
                plan.direct_sources.update(
                    s for s in self.doc_sources_for_table(d) if not meta.doc_sources[s].deprecated)
        else:  # nothing matched: consider every live source
            plan.fallback = True
            for s in meta.doc_sources.values():
                if s.deprecated:
                    drop("source", s.id, "deprecated")
                else:
                    plan.doc_sources.append(s.id)

        for t in plan.tables:
            ups = [e for e in meta.lineage if e["downstream"] == t and not meta.tables[e["upstream"]].deprecated]
            if ups:
                plan.lineage.append(f"{t} is fed by: " + ", ".join(e["upstream"] for e in ups))
        return plan
