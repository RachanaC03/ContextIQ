
"""Command line interface: generate | index | ask | answer | sql | audit."""

from __future__ import annotations

import argparse
import os
import sys

from .config import Settings
from .engine import ContextEngine
from .governance.policy import AccessDenied, UnknownRoleError
from .synth.generate import generate


def _print_bundle(b) -> None:
    print(f"Role: {b.role} | mode: {b.mode}")

    if b.mode == "graph":
        print(
            f"Resolved: periods={b.periods or '-'} "
            f"products={b.products or '-'} terms={b.terms or '-'}"
        )
        print(f"Readable tables: {', '.join(b.schemas) or '-'}")

        for d in b.dropped_deprecated:
            print(
                f"Dropped before search: {d['kind']} "
                f"{d['id']} ({d['reason']})"
            )

    print(f"\nEvidence ({len(b.evidence)} chunks):")

    for i, e in enumerate(b.evidence, 1):
        print(
            f" {i:>2}. [{e.score:.3f}] "
            f"{e.source_id:<16} {e.title} ({e.doc_id})"
        )

    if b.mode == "graph":
        print(f"\nAccess notice: {b.access_notice}")
    else:
        n = len(b.violations)
        print(
            f"\nPOLICY VIOLATIONS: {n} of "
            f"{len(b.evidence)} chunks should not have "
            f"been shown to this role."
        )

        for v in b.violations:
            print(f"  LEAK: {v['doc_id']} - {v['reason']}")


def _print_rows(res) -> None:
    widths = [
        max(len(str(x)) for x in [c] + [r[i] for r in res.rows])
        for i, c in enumerate(res.columns)
    ]

    print("  ".join(c.ljust(w) for c, w in zip(res.columns, widths)))
    print("  ".join("-" * w for w in widths))

    for r in res.rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(res.columns, widths)))

    print(
        f"({len(res.rows)} rows"
        f"{', truncated' if res.truncated else ''})"
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="contextiq",
        description="Governed, context-aware retrieval layer.",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "generate",
        help="generate synthetic tables, documents and ground truth",
    )

    sub.add_parser(
        "index",
        help="chunk, embed and index documents into ChromaDB",
    )

    a = sub.add_parser(
        "ask",
        help="retrieve governed context for a question",
    )
    a.add_argument("question")
    a.add_argument("--role", default="support_analyst")
    a.add_argument(
        "--plain",
        action="store_true",
        help="baseline: plain vector search that ignores roles",
    )
    a.add_argument(
        "--prompt",
        action="store_true",
        help="print the grounded context an LLM would receive",
    )
    a.add_argument("--top-k", type=int, default=8)

    answer = sub.add_parser(
        "answer",
        help="generate an evidence-grounded answer using local Ollama and LangGraph",
    )
    answer.add_argument("question")
    answer.add_argument("--role", default="support_analyst")
    answer.add_argument("--top-k", type=int, default=8)
    answer.add_argument(
        "--model",
        default=os.getenv("CONTEXTIQ_LLM_MODEL", "qwen2.5:1.5b"),
    )

    s = sub.add_parser(
        "sql",
        help="run a guarded, read-only SQL query",
    )
    s.add_argument("query")
    s.add_argument("--role", default="support_analyst")

    u = sub.add_parser(
        "audit",
        help="show recent audit log entries",
    )
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
            bundle = engine.ask(
                args.question,
                args.role,
                plain=args.plain,
                top_k=args.top_k,
            )

            if args.prompt:
                print(bundle.to_prompt())
            else:
                _print_bundle(bundle)

        elif args.cmd == "answer":
            from .agents.workflow import answer_question

            try:
                result = answer_question(
                    engine=engine,
                    question=args.question,
                    role=args.role,
                    top_k=args.top_k,
                    model=args.model,
                )
            except Exception as exc:
                sys.exit(
                    f"LLM request failed: {exc}\n"
                    "Check that Ollama is running and the requested "
                    "model is installed."
                )

            print(f"Role: {result['role']}")
            print(f"Model: {args.model}")
            print("\nAnswer:")
            print(result["answer"])

            print(
                f"\nCitation validation: "
                f"{result['citation_status']}"
            )

            bundle = result.get("bundle")

            if bundle and bundle.evidence:
                print("\nRetrieved evidence:")

                for i, evidence in enumerate(bundle.evidence, 1):
                    print(
                        f"[{i}] {evidence.title} "
                        f"({evidence.source_id}, {evidence.month})"
                    )

            if result["citation_status"] == "missing_citations":
                print(
                    "\nWarning: The answer contains no numbered "
                    "evidence citations. Please review it."
                )

        elif args.cmd == "sql":
            _print_rows(engine.sql(args.query, args.role))

        elif args.cmd == "audit":
            for r in engine.audit.recent(args.limit):
                print(
                    f"{r['id']:>4} {r['ts']} "
                    f"{r['role']:<16} {r['action']:<16} "
                    f"{r['decision']:<5} "
                    f"{r['resource'][:48]:<48} "
                    f"{r['reason'] or ''}"
                )

    except UnknownRoleError as exc:
        sys.exit(f"error: {exc}")

    except AccessDenied as exc:
        print(f"DENIED: {exc.reason}")
        sys.exit(2)


if __name__ == "__main__":
    main()
