"""Append-only audit log of every allow/deny decision."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('allow', 'deny')),
    reason TEXT,
    detail TEXT
)
"""


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def record(self, role: str, action: str, resource: str, decision: str,
               reason: str = "", detail: dict | None = None) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO audit_log (ts, role, action, resource, decision, reason, detail) "
                "VALUES (?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), role, action, resource,
                 decision, reason, json.dumps(detail) if detail else None))

    def recent(self, limit: int = 20, decision: str | None = None, role: str | None = None) -> list[dict]:
        sql, args = "SELECT id, ts, role, action, resource, decision, reason FROM audit_log", []
        clauses = []
        if decision:
            clauses.append("decision = ?")
            args.append(decision)
        if role:
            clauses.append("role = ?")
            args.append(role)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            cur = c.execute(sql, args)
            names = [d[0] for d in cur.description]
            return [dict(zip(names, row)) for row in cur.fetchall()]

    def count(self, decision: str | None = None, action: str | None = None) -> int:
        sql, args, clauses = "SELECT COUNT(*) FROM audit_log", [], []
        if decision:
            clauses.append("decision = ?")
            args.append(decision)
        if action:
            clauses.append("action = ?")
            args.append(action)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._conn() as c:
            return c.execute(sql, args).fetchone()[0]
