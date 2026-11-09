"""ChromaDB-backed vector store with metadata filtering."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings


@dataclass
class Hit:
    chunk_id: str
    text: str
    metadata: dict
    similarity: float


def and_filters(*clauses: dict | None) -> dict | None:
    parts = [c for c in clauses if c]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else {"$and": parts}


class VectorStore:
    def __init__(self, path: Path, embedder) -> None:
        self.embedder = embedder
        self.client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False))
        self.name = f"docs_{embedder.name}"
        self.col = self._open()

    def _open(self):
        return self.client.get_or_create_collection(self.name, metadata={"hnsw:space": "cosine"})

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.name)
        except Exception:  # noqa: BLE001 - collection may not exist yet
            pass
        self.col = self._open()

    def count(self) -> int:
        return self.col.count()

    def add_chunks(self, chunks: list[dict], batch: int = 64) -> None:
        for i in range(0, len(chunks), batch):
            part = chunks[i:i + batch]
            self.col.add(
                ids=[c["id"] for c in part],
                documents=[c["text"] for c in part],
                metadatas=[c["metadata"] for c in part],
                embeddings=self.embedder.embed([c["embed_text"] for c in part]),
            )

    def query(self, text: str, n: int = 5, where: dict | None = None) -> list[Hit]:
        total = self.col.count()
        if total == 0:
            return []
        res = self.col.query(
            query_embeddings=self.embedder.embed([text]),
            n_results=min(n, total),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return [
            Hit(chunk_id=i, text=d, metadata=m, similarity=round(1.0 - dist, 4))
            for i, d, m, dist in zip(res["ids"][0], res["documents"][0],
                                     res["metadatas"][0], res["distances"][0])
        ]
