"""Data models shared by the governed and plain retrievers."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Evidence:
    chunk_id: str
    doc_id: str
    title: str
    source_id: str
    tier: str
    month: str
    score: float
    vector_score: float
    text: str
    boosts: dict[str, float] = field(default_factory=dict)


@dataclass
class ContextBundle:
    question: str
    role: str
    mode: str                                   # "graph" (governed) or "plain" (baseline)
    periods: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    definitions: list[dict] = field(default_factory=list)
    schemas: dict[str, list[dict]] = field(default_factory=dict)   # only columns the role may read
    lineage: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    withheld: list[dict] = field(default_factory=list)             # internal: never shown to the model
    dropped_deprecated: list[dict] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)

    @property
    def access_notice(self) -> str:
        n = len(self.withheld)
        if n == 0:
            return "No sources were withheld by access policy."
        return (f"{n} source(s) relevant to this question were withheld because of the role's permissions. "
                f"Do not speculate about their content.")

    def to_prompt(self) -> str:
        """The grounded context an LLM would receive. Withheld sources are counted, never described."""
        out = [f'You are answering a business question for a user with the role "{self.role}". '
               "Use ONLY the context below, cite evidence by its [number], and say when evidence is missing.",
               "", "## Question", self.question, "", "## Resolved",
               f"Periods: {', '.join(self.periods) or 'none'} | Products: {', '.join(self.products) or 'none'} "
               f"| Business terms: {', '.join(self.terms) or 'none'}"]
        if self.definitions:
            out += ["", "## Definitions"]
            out += [f"- {d['term']}: {d['definition']} (authoritative table: {d['table']})" for d in self.definitions]
        if self.schemas:
            out += ["", "## Readable data (columns this role may query)"]
            for table, cols in self.schemas.items():
                out.append(f"- {table}: " + ", ".join(f"{c['name']} ({c['type']})" for c in cols))
        if self.lineage:
            out += ["", "## Lineage"] + [f"- {line}" for line in self.lineage]
        out += ["", "## Evidence"]
        if not self.evidence:
            out.append("(no evidence available to this role)")
        for i, e in enumerate(self.evidence, 1):
            out.append(f"[{i}] {e.title} (source: {e.source_id}, doc: {e.doc_id}, period: {e.month})")
            out.append(e.text)
            out.append("")
        out += ["## Access notice", self.access_notice]
        return "\n".join(out)
