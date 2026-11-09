"""SQL guard: parse with sqlglot and allow only a single, read-only SELECT on catalogued,
non-deprecated tables and columns that the caller's role may see."""
from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from ..metadata import Metadata
from .policy import AccessPolicy

_DANGEROUS_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


@dataclass
class GuardResult:
    allowed: bool
    reason: str
    tables: list[str] = field(default_factory=list)


def _deny(reason: str, tables: list[str] | None = None) -> GuardResult:
    return GuardResult(False, reason, tables or [])


class SQLGuard:
    def __init__(self, meta: Metadata, policy: AccessPolicy) -> None:
        self.meta = meta
        self.policy = policy

    def check(self, sql: str, role: str) -> GuardResult:
        self.policy.require_role(role)  # raises UnknownRoleError for a bad role
        try:
            statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
        except sqlglot.errors.SqlglotError as exc:
            return _deny(f"could not parse SQL: {str(exc).splitlines()[0]}")
        if len(statements) != 1:
            return _deny("exactly one statement is allowed")
        stmt = statements[0]
        if not isinstance(stmt, exp.Select):
            return _deny(f"only a single SELECT is allowed (got {stmt.key.upper()})")

        for fn in stmt.find_all(exp.Anonymous):
            if str(fn.this).lower() in _DANGEROUS_FUNCTIONS:
                return _deny(f"function {fn.this} is not allowed")

        derived = {c.alias_or_name for c in stmt.find_all(exp.CTE)}
        derived |= {s.alias for s in stmt.find_all(exp.Subquery) if s.alias}
        output_names = {a.alias for a in stmt.find_all(exp.Alias) if a.alias}

        # ---- tables
        alias_map: dict[str, str] = {}
        tables: list[str] = []
        for t in stmt.find_all(exp.Table):
            if not isinstance(t.this, exp.Identifier):
                return _deny("table-valued functions are not allowed")
            name = t.name
            if name in derived and not t.args.get("db"):
                continue  # reference to a CTE, validated through its own SELECT
            table = self.meta.tables.get(name)
            if table is None:
                return _deny(f"table '{name}' is not in the catalog", tables)
            if table.deprecated:
                hint = f"; use {table.superseded_by} instead" if table.superseded_by else ""
                return _deny(f"table '{name}' is deprecated{hint}", tables)
            if self.policy.table_columns(role, name) is None:
                return _deny(f"role '{role}' may not read table '{name}'", tables)
            alias_map[t.alias_or_name] = name
            if name not in tables:
                tables.append(name)

        # ---- stars
        for star in stmt.find_all(exp.Star):
            if isinstance(star.parent, exp.Count):
                continue
            scope = tables
            if isinstance(star.parent, exp.Column) and star.parent.table:
                q = star.parent.table
                if q in derived:
                    continue
                if q not in alias_map:
                    return _deny(f"unknown table or alias '{q}'", tables)
                scope = [alias_map[q]]
            for tname in scope:
                allowed = set(self.policy.table_columns(role, tname) or [])
                hidden = [c for c in self.meta.tables[tname].columns if c not in allowed]
                if hidden:
                    return _deny(
                        f"SELECT * on '{tname}' is not allowed for role '{role}' "
                        f"(restricted columns: {', '.join(hidden)}); list columns explicitly", tables)

        # ---- columns
        for col in stmt.find_all(exp.Column):
            if isinstance(col.this, exp.Star):
                continue
            name, qualifier = col.name, col.table
            if qualifier:
                if qualifier in derived:
                    continue
                if qualifier not in alias_map:
                    return _deny(f"unknown table or alias '{qualifier}'", tables)
                candidates = [alias_map[qualifier]]
            else:
                candidates = [t for t in tables if name in self.meta.tables[t].columns]
                if not candidates:
                    if name in output_names or name in derived:
                        continue  # alias or derived column
                    return _deny(f"unknown column '{name}'", tables)
            for tname in candidates:
                if name not in self.meta.tables[tname].columns:
                    return _deny(f"column '{tname}.{name}' is not in the catalog", tables)
                if name not in (self.policy.table_columns(role, tname) or []):
                    return _deny(f"column '{tname}.{name}' is restricted for role '{role}'", tables)

        return GuardResult(True, "allowed", tables)
