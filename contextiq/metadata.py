"""Loads and validates the hand-authored context metadata (catalog, glossary, lineage, roles)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    description: str = ""
    sensitivity: str = "normal"


@dataclass(frozen=True)
class Table:
    name: str
    description: str
    owner: str
    deprecated: bool
    superseded_by: str | None
    columns: dict[str, Column]


@dataclass(frozen=True)
class DocSource:
    id: str
    tier: str
    description: str
    deprecated: bool
    linked_tables: tuple[str, ...]


@dataclass(frozen=True)
class Term:
    id: str
    definition: str
    synonyms: tuple[str, ...]
    defines: str


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    aliases: tuple[str, ...]


@dataclass
class Metadata:
    tiers: list[str]
    tables: dict[str, Table]
    doc_sources: dict[str, DocSource]
    terms: dict[str, Term]
    products: dict[str, Product]
    lineage: list[dict]
    roles: dict[str, dict] = field(default_factory=dict)

    def validate(self) -> None:
        """Raise ValueError if the hand-authored metadata is inconsistent."""
        errors: list[str] = []
        for t in self.tables.values():
            if t.superseded_by and t.superseded_by not in self.tables:
                errors.append(f"table {t.name}: superseded_by {t.superseded_by} is not catalogued")
        for s in self.doc_sources.values():
            if s.tier not in self.tiers:
                errors.append(f"doc source {s.id}: unknown tier {s.tier}")
            for lt in s.linked_tables:
                if lt not in self.tables:
                    errors.append(f"doc source {s.id}: linked table {lt} is not catalogued")
        for term in self.terms.values():
            if term.defines not in self.tables:
                errors.append(f"term {term.id}: defines unknown table {term.defines}")
        for e in self.lineage:
            for end in ("upstream", "downstream"):
                if e[end] not in self.tables:
                    errors.append(f"lineage edge references unknown table {e[end]}")
        for name, role in self.roles.items():
            for tier in role.get("tiers", []):
                if tier not in self.tiers:
                    errors.append(f"role {name}: unknown tier {tier}")
            tables = role.get("tables", {})
            if tables == "*":
                continue
            for tname, spec in tables.items():
                if tname not in self.tables:
                    errors.append(f"role {name}: unknown table {tname}")
                    continue
                if isinstance(spec, dict):
                    for col in spec.get("deny_columns", []):
                        if col not in self.tables[tname].columns:
                            errors.append(f"role {name}: {tname}.{col} does not exist")
                elif spec != "all":
                    errors.append(f"role {name}: bad table spec for {tname}: {spec!r}")
        if errors:
            raise ValueError("Invalid context metadata:\n- " + "\n- ".join(errors))


def load_metadata(context_dir: Path) -> Metadata:
    context_dir = Path(context_dir)
    catalog = yaml.safe_load((context_dir / "catalog.yaml").read_text())
    glossary = yaml.safe_load((context_dir / "glossary.yaml").read_text())
    lineage = json.loads((context_dir / "lineage.json").read_text())["edges"]
    roles = yaml.safe_load((context_dir / "roles.yaml").read_text())["roles"]

    tables = {}
    for name, spec in catalog["tables"].items():
        cols = {
            cname: Column(
                name=cname,
                type=c.get("type", "TEXT"),
                description=c.get("description", ""),
                sensitivity=c.get("sensitivity", "normal"),
            )
            for cname, c in spec["columns"].items()
        }
        tables[name] = Table(
            name=name,
            description=" ".join(str(spec.get("description", "")).split()),
            owner=spec.get("owner", ""),
            deprecated=bool(spec.get("deprecated", False)),
            superseded_by=spec.get("superseded_by"),
            columns=cols,
        )

    doc_sources = {
        sid: DocSource(
            id=sid,
            tier=s["tier"],
            description=s.get("description", ""),
            deprecated=bool(s.get("deprecated", False)),
            linked_tables=tuple(s.get("linked_tables", [])),
        )
        for sid, s in catalog["doc_sources"].items()
    }
    terms = {
        tid: Term(
            id=tid,
            definition=" ".join(str(t["definition"]).split()),
            synonyms=tuple(t["synonyms"]),
            defines=t["defines"],
        )
        for tid, t in glossary["terms"].items()
    }
    products = {
        pid: Product(id=pid, name=p["name"], aliases=tuple(p.get("aliases", [])))
        for pid, p in glossary["products"].items()
    }
    meta = Metadata(
        tiers=list(catalog["tiers"]),
        tables=tables,
        doc_sources=doc_sources,
        terms=terms,
        products=products,
        lineage=lineage,
        roles=roles,
    )
    meta.validate()
    return meta
