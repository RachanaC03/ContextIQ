"""Role-based access policy, enforced in code (never by asking a prompt to behave)."""
from __future__ import annotations

from ..metadata import Metadata


class UnknownRoleError(KeyError):
    pass


class AccessDenied(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class AccessPolicy:
    def __init__(self, meta: Metadata) -> None:
        self.meta = meta

    def roles(self) -> list[str]:
        return sorted(self.meta.roles)

    def require_role(self, role: str) -> dict:
        try:
            return self.meta.roles[role]
        except KeyError:
            raise UnknownRoleError(f"unknown role: {role!r} (known: {', '.join(self.roles())})") from None

    def tiers(self, role: str) -> list[str]:
        return list(self.require_role(role).get("tiers", []))

    def can_read_source(self, role: str, source_id: str) -> tuple[bool, str]:
        spec = self.require_role(role)
        source = self.meta.doc_sources.get(source_id)
        if source is None:
            return False, "unknown source"
        if source.tier not in spec.get("tiers", []):
            return False, f"tier '{source.tier}' is not permitted for role '{role}'"
        return True, "tier permitted"

    def table_columns(self, role: str, table: str) -> list[str] | None:
        """Columns of `table` the role may read, or None if the whole table is off limits."""
        spec = self.require_role(role).get("tables", {})
        tbl = self.meta.tables.get(table)
        if tbl is None:
            return None
        every = list(tbl.columns)
        if spec == "*":
            return every
        rule = spec.get(table)
        if rule is None:
            return None
        if rule == "all":
            return every
        denied = set(rule.get("deny_columns", []))
        return [c for c in every if c not in denied]

    def can_read_table(self, role: str, table: str) -> bool:
        return self.table_columns(role, table) is not None
