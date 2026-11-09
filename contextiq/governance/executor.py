"""Governed SQL executor: guard -> read-only connection -> SQLite authorizer -> audit log.

Two independent layers protect column-level access: the sqlglot guard (clear error messages)
and a SQLite authorizer (blocks reads even if the guard were bypassed)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..config import Settings
from ..metadata import Metadata
from .audit import AuditLog
from .policy import AccessDenied, AccessPolicy
from .sql_guard import SQLGuard

_ROWID = {"rowid", "oid", "_rowid_"}


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool


class GovernedSQL:
    def __init__(self, settings: Settings, meta: Metadata, policy: AccessPolicy,
                 guard: SQLGuard, audit: AuditLog) -> None:
        self.settings, self.meta, self.policy, self.guard, self.audit = settings, meta, policy, guard, audit

    def _authorizer(self, role: str):
        allowed = {t: {c.lower() for c in cols}
                   for t in self.meta.tables
                   if not self.meta.tables[t].deprecated
                   and (cols := self.policy.table_columns(role, t)) is not None}

        def auth(action, arg1, arg2, dbname, source):
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ:
                if arg1 not in allowed:
                    return sqlite3.SQLITE_DENY
                if arg2 and arg2.lower() not in allowed[arg1] and arg2.lower() not in _ROWID:
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        return auth

    def _execute(self, sql: str, role: str, max_rows: int) -> QueryResult:
        conn = sqlite3.connect(f"file:{self.settings.db_path}?mode=ro", uri=True)
        try:
            conn.execute("PRAGMA query_only = ON")
            conn.set_authorizer(self._authorizer(role))
            cur = conn.execute(sql)
            rows = cur.fetchmany(max_rows + 1)
            return QueryResult([d[0] for d in cur.description], rows[:max_rows], len(rows) > max_rows)
        finally:
            conn.close()

    def run(self, sql: str, role: str, max_rows: int = 200) -> QueryResult:
        verdict = self.guard.check(sql, role)
        if not verdict.allowed:
            self.audit.record(role, "sql", sql, "deny", verdict.reason)
            raise AccessDenied(verdict.reason)
        try:
            result = self._execute(sql, role, max_rows)
        except sqlite3.DatabaseError as exc:
            reason = f"database refused the query: {exc}"
            self.audit.record(role, "sql", sql, "deny", reason)
            raise AccessDenied(reason) from exc
        self.audit.record(role, "sql", sql, "allow", "guard passed",
                          {"tables": verdict.tables, "rows": len(result.rows)})
        return result
