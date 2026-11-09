# ContextIQ: governed, context-aware agent platform

A production-oriented prototype (synthetic data) showing that AI agents answer better, and more safely, when they
retrieve through governed metadata (definitions, lineage, ownership, access policies) instead of raw vector search.

**Status:** Weeks 1-2 complete (data, context graph, governed retrieval, SQL guard, audit log, 122 tests).
Agents, API, UI, observability and evaluation are next (see roadmap).

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m contextiq generate     # synthetic tables, documents, ground truth  -> data/generated/
python -m contextiq index        # chunk + embed + index into ChromaDB
pytest                           # 122 tests

Q="Why did customer complaints increase last month, which products were affected, and what should we do?"
python -m contextiq ask "$Q" --role support_analyst            # governed, graph-based retrieval
python -m contextiq ask "$Q" --role finance_manager            # same question, different permitted evidence
python -m contextiq ask "$Q" --plain --role finance_manager    # baseline: ignores roles (leaks)
python -m contextiq ask "$Q" --role support_analyst --prompt   # the grounded context an LLM would receive

python -m contextiq sql "SELECT product_id, complaint_rate_pct FROM complaints_monthly WHERE month='2026-10' ORDER BY 2 DESC" --role support_analyst
python -m contextiq sql "SELECT unit_price FROM orders" --role support_analyst    # denied: column-level policy
python -m contextiq audit
```
Roles: `support_analyst`, `quality_engineer`, `finance_manager`, `executive` (see `data/context/roles.yaml`).

**Embeddings:** `EMBEDDER=auto` (default) tries `sentence-transformers/all-MiniLM-L6-v2` and falls back to a
deterministic hashing embedder if the package or model is unavailable. `EMBEDDER=hash` forces the fallback and
`EMBEDDER=st` forces the real model (`pip install sentence-transformers` first).

## The synthetic world and its planted ground truth
Hearthline sells 8 small appliances. Jan-Oct 2026 data (20,000 orders, 380 complaints) contains a known story:

- **P-104 AeroBrew Pro:** production batch `B-2026-09B` has a faulty heating element from a new supplier. Complaint
  rate jumps from about 3.9% to about 16% in October; every October P-104 complaint traces to that batch.
- **P-107 Robo Vac R2:** a carrier change causes delivery-delay complaints (a confounder; second most affected).
- **`legacy_complaint_stats`** is a deprecated, stale table with a different metric definition (a decoy).

Documents span four access tiers (general, support, quality, finance). `ground_truth.json` is computed from the
generated data and is what the Week 5 evaluation will score against.

## How it works
```
question
  -> resolve business terms (glossary), products, time periods ("last month" -> 2026-10)
  -> walk the context graph: term -defines-> authoritative table -fed_by-> upstream tables -> linked documents
       (deprecated sources are dropped here, before any search; a deprecated table is replaced by its successor)
  -> permission check per source, per role (denied sources are recorded as "withheld", never described to the model)
  -> per-source vector search (time-filtered) -> graph-aware re-ranking -> per-source cap
  -> ContextBundle: evidence + definitions + readable schemas + lineage + access notice
SQL: parse (sqlglot) -> single SELECT only -> catalogued, non-deprecated, permitted tables and columns
     -> read-only SQLite connection with an authorizer as a second layer
Everything allowed or denied is written to `audit_log`.
```

| Path | Purpose |
|---|---|
| `data/context/` | Hand-authored metadata: `catalog.yaml`, `glossary.yaml`, `lineage.json`, `roles.yaml` |
| `contextiq/synth/` | Synthetic data and document generator, planted ground truth |
| `contextiq/context/` | Chunking/ingestion, embedders, ChromaDB store, context graph (networkx) |
| `contextiq/retrieval/` | `plain_rag` (baseline), `graph_rag` (governed), temporal resolver, violation checks |
| `contextiq/governance/` | Access policy, SQL guard, governed executor, audit log |
| `contextiq/engine.py` | `ContextEngine` facade used by the CLI (and later agents and the API) |
| `tests/` | Data, metadata, governance, graph and retrieval tests |

## Design decisions worth defending
- Permissions are enforced in code at retrieval and query time, never by asking the prompt to behave.
- Withheld sources are counted, not described: the model-facing context never names them, and even the lineage text
  hides restricted upstream tables.
- Deprecated sources are excluded by the graph, not by hoping the model ignores them.
- Column-level SQL access is enforced twice (sqlglot guard, then a SQLite authorizer), so a guard bug alone cannot leak a column.
- Per-source retrieval plus a per-source cap: a large, repetitive source cannot crowd out the rest of the evidence.
- The plain RAG baseline shares the same index, so the evaluation isolates the effect of governed context.

## Known limitations (be upfront about these)
- Developed and tested with SQLite and the hashing fallback embedder. The MiniLM embedder path is implemented but has
  **not** been exercised yet; run `EMBEDDER=st pytest` locally after installing `sentence-transformers`.
- With the hashing embedder, retrieval is essentially lexical. Real embeddings should rank semantically related
  documents better; check this before trusting evaluation numbers.
- Term linking is lexical (glossary synonyms). Embedding- or LLM-based linking is a natural extension.
- Only SQLite is supported; PostgreSQL is not implemented.
- Governed retrieval has zero permission violations by construction; the interesting evaluation metrics will be
  faithfulness, citation accuracy and wrong-source rate.

## Roadmap
- Week 3: LangGraph agents (retrieval, analysis, action) with an LLM; structured citations; SQL tool via the guard.
- Week 4: approval gate, FastAPI, Streamlit UI with a role selector.
- Week 5: tracing; 30-50 question test set; RAGAS + custom metrics; plain vs graph comparison.
- Week 6: optional MCP server for the context layer, deployment, demo video.
