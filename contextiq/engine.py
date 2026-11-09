"""ContextEngine: the facade used by the CLI (and, later, agents and an API)."""
from __future__ import annotations

from .config import Settings
from .context.embedders import get_embedder
from .context.graph import ContextGraph
from .context.ingest import build_index
from .context.store import VectorStore
from .governance.audit import AuditLog
from .governance.executor import GovernedSQL, QueryResult
from .governance.policy import AccessPolicy
from .governance.sql_guard import SQLGuard
from .metadata import load_metadata
from .retrieval.graph_rag import GovernedRetriever
from .retrieval.models import ContextBundle
from .retrieval.plain_rag import PlainRetriever


class ContextEngine:
    def __init__(self, settings: Settings | None = None, embedder=None) -> None:
        self.settings = settings or Settings()
        self.settings.ensure_dirs()
        self.meta = load_metadata(self.settings.context_dir)
        self.policy = AccessPolicy(self.meta)
        self.graph = ContextGraph(self.meta)
        self.audit = AuditLog(self.settings.audit_path)
        self.embedder = embedder or get_embedder(self.settings.embedder)
        self.store = VectorStore(self.settings.chroma_dir, self.embedder)
        self.guard = SQLGuard(self.meta, self.policy)
        self.sql_executor = GovernedSQL(self.settings, self.meta, self.policy, self.guard, self.audit)
        self.governed = GovernedRetriever(self.meta, self.graph, self.policy, self.store, self.audit,
                                          self.settings.as_of)
        self.plain = PlainRetriever(self.meta, self.policy, self.store)

    def index(self) -> dict:
        return build_index(self.settings, self.store, self.meta)

    def ask(self, question: str, role: str, plain: bool = False, top_k: int = 8) -> ContextBundle:
        retriever = self.plain if plain else self.governed
        return retriever.retrieve(question, role, top_k=top_k)

    def sql(self, query: str, role: str, max_rows: int = 200) -> QueryResult:
        return self.sql_executor.run(query, role, max_rows=max_rows)
