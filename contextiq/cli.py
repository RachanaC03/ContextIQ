"""Command line interface: generate | index | ask | sql | audit."""
from __future__ import annotations

import argparse
import sys

from .config import Settings
from .engine import ContextEngine
from .governance.policy import AccessDenied, UnknownRoleError
from .synth.generate import generate


def _print_bundle(b) -> None:
    print(f"Role: {b.role} | mode: {b.mode}")
    if b.mode == "graph":
        print(f"Resolved: periods={b.periods or '-'} products={b.products or '-'} terms={b.terms or '-'}")
        print(f"Readable tables: {', '.join(b.schemas) or '-'}")
        for d in b.dropped_deprecated:
            print(f"Dropped before search: {d['kind']} {d['id']} ({d['reason']})")
    print(f"\nEvidence ({len(b.evidence)} chunks):")
    for i, e in enumerate(b.evidence, 1):
        print(f" {i:>2}. [{e.score:.3f}] {e.source_id:<16} {e.title}  ({e.doc_id})")
    if b.mode == "graph":
        print(f"\nAccess notice: {b.access_notice}")
    else:
        n = len(b.violations)
        print(f"\nPOLICY VIOLATIONS: {n} of {len(b.evidence)} chunks should not have been shown to this role.")
        for v in b.violations:
            print(f"  LEAK: {v['doc_id']} - {v['reason']}")


def _print_rows(res) -> None:
    widths = [max(len(str(x)) for x in [c] + [r[i] for r in res.rows]) for i, c in enumerate(res.columns)]
    print("  ".join(c.ljust(w) for c, w in zip(res.columns, widths)))
    print("  ".join("-" * w for w in widths))
    for r in res.rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)))
    print(f"({len(res.rows)} rows{', truncated' if res.truncated else ''})")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="contextiq", description="Governed, context-aware retrieval layer.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate", help="generate synthetic tables, documents and ground truth")
    sub.add_parser("index", help="chunk, embed and index documents into ChromaDB")
    a = sub.add_parser("ask", help="retrieve governed context for a question")
    a.add_argument("question")
    a.add_argument("--role", default="support_analyst")
    a.add_argument("--plain", action="store_true", help="baseline: plain vector search that ignores roles")
    a.add_argument("--prompt", action="store_true", help="print the grounded context an LLM would receive")
    a.add_argument("--top-k", type=int, default=8)
    s = sub.add_parser("sql", help="run a guarded, read-only SQL query")
    s.add_argument("query")
    s.add_argument("--role", default="support_analyst")
    u = sub.add_parser("audit", help="show recent audit log entries")
    u.add_argument("--limit", type=int, default=20)
    args = p.parse_args(argv)

    settings = Settings()
    if args.cmd == "generate":
        print(generate(settings))
        return
    engine = ContextEngine(settings)
    try:
        if args.cmd == "index":
            print(engine.index())
        elif args.cmd == "ask":
            bundle = engine.ask(args.question, args.role, plain=args.plain, top_k=args.top_k)
            print(bundle.to_prompt() if args.prompt else "", end="\n" if args.prompt else "")
            if not args.prompt:
                _print_bundle(bundle)
        elif args.cmd == "sql":
            _print_rows(engine.sql(args.query, args.role))
        elif args.cmd == "audit":
            for r in engine.audit.recent(args.limit):
                print(f"{r['id']:>4} {r['ts']} {r['role']:<16} {r['action']:<16} {r['decision']:<5} "
                      f"{r['resource'][:48]:<48} {r['reason'] or ''}")
    except UnknownRoleError as exc:
        sys.exit(f"error: {exc}")
    except AccessDenied as exc:
        print(f"DENIED: {exc.reason}")
        sys.exit(2)


if __name__ == "__main__":
    main()
