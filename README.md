
# ContextIQ — Governed Business Context & Retrieval Platform

ContextIQ is a Python-based governed retrieval prototype that helps business applications retrieve relevant information while respecting role-based access policies, business metadata, data lineage, and source-level permissions.

Instead of relying only on unrestricted vector search, ContextIQ combines a context graph, metadata-aware retrieval, access control, SQL validation, and local LLM answer generation to produce structured business context and evidence-grounded answers.

**Current status:** Working portfolio prototype using synthetic business data, governed retrieval, SQL validation, a Streamlit dashboard, structured evidence reports, and a local LLM answer workflow orchestrated with LangGraph.

**Automated tests:** 127 passing.

## Features

- **Governed graph-based retrieval:** Uses business metadata and context relationships to identify relevant sources.
- **Role-based access control:** Supports four roles with different evidence permissions.
- **Context graph:** Connects business terms, authoritative tables, upstream data, and related documents.
- **Metadata-aware retrieval:** Uses source-specific vector search, filtering, ranking, and evidence limits.
- **Deprecated-source handling:** Excludes deprecated sources from governed retrieval.
- **Temporal retrieval:** Applies relevant time filters to business questions.
- **Governed SQL execution:** Validates SQL queries against table and column permissions.
- **Audit logging:** Records governance and query activity.
- **Plain RAG baseline:** Provides a retrieval comparison path for experimentation.
- **Evidence-grounded answer reports:** Organizes retrieved evidence into structured findings with numbered citations, resolved context, and limitations.
- **Local LLM integration:** Uses Ollama and the Qwen2.5 1.5B model to generate natural-language answers.
- **LangGraph workflow:** Orchestrates retrieval, conditional answer generation, and citation-reference validation.
- **Interactive dashboard:** Displays retrieval results, evidence, schemas, governance information, and generated reports.

## Architecture

### Governed Retrieval Workflow

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
```

### Local LLM Answer Workflow

```text
Business question
       |
       v
LangGraph workflow
       |
       v
Governed evidence retrieval
       |
       v
Check for permitted evidence
       |
       +------ No evidence ------> Return no-evidence result
       |
       v
Generate answer using local Ollama model
       |
       v
Validate citation references
       |
       v
Return answer and retrieved evidence
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
| LangGraph | Orchestrates the local answer-generation workflow |
| Ollama | Runs the local Qwen2.5 1.5B language model |
| Pytest | Automated testing |
| Sentence Transformers | Optional semantic embeddings |

## Project Structure

```text
ContextIQ/
├── app.py
├── contextiq/
│   ├── agents/
│   │   ├── __init__.py
│   │   └── workflow.py
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
│   ├── test_agent_workflow.py
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

**Latest verified result: 127 passed.**

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

### Local LLM Answer Workflow

ContextIQ also includes a local LLM answer workflow orchestrated with LangGraph.

It uses:

- **Ollama** to run the language model locally.
- **Qwen2.5 1.5B** as the default language model.
- **LangGraph** to orchestrate retrieval, conditional generation, and validation.

Install Ollama separately and make sure it is running.

Download the model:

```cmd
ollama pull qwen2.5:1.5b
```

Generate an answer using the quality engineer role:

```cmd
python -m contextiq answer "Why did complaints increase in October?" --role quality_engineer
```

The workflow:

1. Retrieves permitted evidence using ContextIQ's governed retrieval engine.
2. Checks whether permitted evidence is available.
3. Skips LLM generation when no permitted evidence is found.
4. Generates a natural-language answer using the local Ollama model.
5. Performs basic citation-reference validation.
6. Returns the answer along with retrieved evidence.

The model runs locally through Ollama. A hosted LLM API is not required.

**Citation validation limitation:** Citation validation checks whether referenced evidence numbers exist in the retrieved results. It does not independently verify that every factual claim is supported by its cited source. Generated answers may still contain unsupported statements and require human review.

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
- Use a local LLM to avoid requiring a hosted model API for answer generation.

## Embedding Configuration

ContextIQ supports configurable embedding selection.

The default `auto` setting attempts to use Sentence Transformers and falls back to a deterministic hashing embedder when the optional dependency is unavailable.

The hashing embedder is useful for local testing but is not equivalent to a semantic embedding model.

The Sentence Transformers MiniLM embedding path is implemented but has not yet been fully validated in this environment.

Refer to `.env.example` and the configuration code for embedding settings.

## Current Limitations

- This is a retrieval and answer-generation prototype, not a complete autonomous AI agent.
- The local LLM and LangGraph workflow is a portfolio prototype, not a production agent system.
- Generated answers may contain unsupported statements and require human review.
- Citation validation checks reference-number validity, not claim-level factual support.
- The default hashing embedder is a deterministic fallback and is largely lexical in behaviour.
- The Sentence Transformers MiniLM embedding path requires further validation.
- Business-term linking currently relies on glossary terms and synonyms.
- SQLite is currently supported; PostgreSQL integration is not implemented.
- Evaluation using a larger benchmark, RAGAS, and custom faithfulness metrics requires future work.
- The prototype has not been deployed as a production service or independently security-audited.

## Roadmap

- Improve answer quality and evaluate factual grounding.
- Add claim-level evidence verification.
- Expand workflow testing and reliability.
- Perform retrieval evaluation and benchmarking.
- Explore RAGAS and custom faithfulness evaluation.
- Improve tracing and observability.
- Add additional data-source integrations.
- Explore a FastAPI service and optional MCP integration.
- Prepare a public demonstration video.

## Author

**Rachana C.**

B.Tech — Artificial Intelligence and Machine Learning

Interested in Python, Artificial Intelligence, Machine Learning, NLP, and Generative AI.

[GitHub: RachanaC03](https://github.com/RachanaC03)

ContextIQ is an independently developed portfolio project exploring governed retrieval, metadata engineering, access-aware business intelligence, and local LLM workflows.
