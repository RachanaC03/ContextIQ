# ContextIQ — Governed Business Context & Retrieval Platform

ContextIQ is a Python-based governed retrieval prototype that helps business applications retrieve relevant information while respecting role-based access policies, business metadata, data lineage, and source-level permissions.

Instead of relying only on unrestricted vector search, ContextIQ combines a context graph, metadata-aware retrieval, access control, and SQL validation to produce structured business context.

**Current status:** Working prototype using synthetic business data, governed retrieval, SQL validation, a Streamlit dashboard, and an evidence-grounded answer-reporting module.

**Automated tests:** 124 passing.

## Features

- **Governed graph-based retrieval:** Uses business metadata and context relationships to identify relevant sources.
- **Role-based access control:** Supports four roles with different evidence permissions.
- **Context graph:** Connects business terms, authoritative tables, upstream data, and related documents.
- **Metadata-aware retrieval:** Uses source-specific vector search, filtering, ranking, and evidence limits.
- **Deprecated-source handling:** Excludes deprecated sources from governed retrieval.
- **Governed SQL execution:** Validates SQL queries against table and column permissions.
- **Audit logging:** Records governance and query activity.
- **Plain RAG baseline:** Provides a retrieval comparison path for experimentation.
- **Evidence-grounded answer reports:** Organizes retrieved evidence into structured findings with numbered citations, resolved context, and limitations.
- **Interactive dashboard:** Displays retrieval results, evidence, schemas, governance information, and generated reports.

## Architecture

The main retrieval workflow is:

```text
Business question
       |
       v
Question and context analysis
       |
       v
Context graph and metadata lookup
       |
       v
Source-level permission checks
       |
       v
Time-filtered vector retrieval
       |
       v
Graph-aware ranking and evidence limits
       |
       v
Structured ContextBundle
       |
       v
Evidence-grounded answer report
       |
       v
Streamlit dashboard
```

The SQL workflow is separate and includes query parsing, permission validation, read-only execution, and database-level authorization.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application and retrieval logic |
| ChromaDB | Vector storage and retrieval |
| NetworkX | Context graph |
| SQLGlot | SQL parsing and validation |
| SQLite | Synthetic business data and governed SQL execution |
| Streamlit | Interactive dashboard |
| PyYAML | Metadata and access-policy configuration |
| Pytest | Automated testing |
| Sentence Transformers | Optional semantic embeddings |

## Project Structure

```text
ContextIQ/
├── app.py
├── contextiq/
│   ├── answering/
│   │   ├── __init__.py
│   │   └── generator.py
│   ├── context/
│   ├── governance/
│   ├── retrieval/
│   ├── synth/
│   ├── config.py
│   ├── engine.py
│   ├── metadata.py
│   └── cli.py
├── data/
├── tests/
│   ├── test_answering.py
│   ├── test_audit.py
│   ├── test_data.py
│   ├── test_executor.py
│   ├── test_graph.py
│   ├── test_metadata.py
│   ├── test_policy.py
│   ├── test_retrieval.py
│   ├── test_sql_guard.py
│   └── test_temporal.py
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── pytest.ini
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/RachanaC03/ContextIQ.git
cd ContextIQ
```

### 2. Create and activate a virtual environment

Windows CMD:

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```cmd
pip install -r requirements.txt
```

### 4. Generate synthetic business data

```cmd
python -m contextiq generate

```

This generates synthetic business tables, documents, and ground-truth data.

### 5. Build the retrieval index

```cmd
python -m contextiq index
```

This processes documents, creates chunks, and indexes them in ChromaDB.

### 6. Run automated tests

```cmd
pytest -q
```

**Latest verified result: 124 passed.**

### 7. Run the Streamlit dashboard

```cmd
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## Using ContextIQ

### Supported Roles

| Role | Intended access |
|---|---|
| `support_analyst` | Customer complaints and support information |
| `quality_engineer` | Product quality and incident information |
| `finance_manager` | Financial and business information |
| `executive` | Executive-level business information |

Role policies are configured in the metadata configuration files.

### Example Business Question

"Why did customer complaints increase last month, which products were affected, and what should we do?"

The governed retrieval workflow identifies relevant periods, products, business terms, and permitted sources before returning evidence.

### Evidence-Grounded Answer Reports

The answering module organizes retrieved evidence into:

- A retrieval summary.
- Numbered evidence citations.
- Source and document references.
- Relevant periods and products.
- Report limitations.
- Access-policy notice.

This module currently creates a structured evidence report. It does not yet generate complete LLM-based business answers or independently establish root causes.

### Plain RAG Baseline

ContextIQ includes a plain retrieval baseline for comparing retrieval behaviour.

It is intended for controlled experimentation, not as a secure alternative to governed retrieval.

### Governed SQL

The SQL execution workflow includes:

1. SQL parsing and validation using SQLGlot.
2. Single-SELECT query restrictions.
3. Table and column permission checks.
4. Read-only SQLite execution.
5. SQLite authorizer as an additional enforcement layer.

### Audit Information

Audit logging records relevant governance and query activity.

## Synthetic Business Scenario

ContextIQ uses a fictional appliance company called **Hearthline**.

The generated dataset contains:

- 20,000 synthetic orders.
- 380 synthetic complaints.
- 57 business documents.
- 8 products.
- Four information access tiers: general, support, quality, and finance.
- Business metadata, lineage information, and ground-truth data.

### Planted Scenarios

**P-104 — AeroBrew Pro**

A faulty heating element associated with production batch `B-2026-09B` and supplier Zenvolt Components is linked to an increase in October complaints.

**P-107 — Robo Vac R2**

A carrier change contributes to delivery-delay complaints.

**Deprecated source — `legacy_complaint_stats`**

Contains stale information and a different metric definition.

These scenarios provide test cases for product discovery, temporal retrieval, source selection, and deprecated-source handling.

All generated data is synthetic. No real customer information is used.

## Design Decisions

- Enforce access policies in application logic rather than relying only on prompt instructions.
- Check permissions at the source level before retrieving evidence.
- Use business metadata and graph relationships to guide source discovery.
- Exclude deprecated sources from governed retrieval.
- Apply time filters and per-source retrieval limits to reduce irrelevant or repetitive evidence.
- Apply SQL validation and database-level authorization as separate enforcement layers.
- Maintain a plain RAG baseline to compare retrieval behaviour.
- Keep answer reporting grounded in retrieved evidence and expose limitations instead of inventing unsupported conclusions.

## Embedding Configuration

ContextIQ supports configurable embedding selection.

The default `auto` setting attempts to use Sentence Transformers and falls back to a deterministic hashing embedder when the optional dependency is unavailable.

The hashing embedder is useful for local testing but is not equivalent to a semantic embedding model.

The Sentence Transformers MiniLM path is implemented but has not yet been fully validated in this environment.

Refer to `.env.example` and the configuration code for embedding settings.

## Current Limitations

- This is a retrieval prototype, not a complete autonomous AI agent.
- LLM-based answer generation and agent orchestration are not yet implemented.
- The current answer generator produces structured evidence reports, not full natural-language business recommendations.
- The default hashing embedder is a deterministic fallback and is largely lexical in behaviour.
- The Sentence Transformers MiniLM embedding path requires further validation.
- Business-term linking currently relies on glossary terms and synonyms.
- SQLite is currently supported; PostgreSQL integration is not implemented.
- Evaluation using a larger benchmark, RAGAS, and custom faithfulness metrics requires future work.
- The prototype has not been deployed as a production service or independently security-audited.

## Roadmap

### Planned

- LLM integration and grounded natural-language answer generation.
- Structured business findings and qualified recommendations.
- LangGraph-based agent workflows.
- Retrieval evaluation and benchmarking.
- RAGAS and custom faithfulness evaluation.
- Improved tracing and observability.
- Additional data-source integrations.

### Future Possibilities

- FastAPI service.
- Optional MCP integration.
- Deployment and demonstration video.
- Expanded database support and evaluation datasets.

## Author

**Rachana C.**

B.Tech — Artificial Intelligence and Machine Learning

Interested in Python, Artificial Intelligence, Machine Learning, NLP, and Generative AI.

[GitHub: RachanaC03](https://github.com/RachanaC03)

ContextIQ is an independently developed portfolio project exploring governed retrieval, metadata engineering, and access-aware business intelligence.