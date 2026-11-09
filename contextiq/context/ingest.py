"""Chunk generated documents and index them into the vector store."""
from __future__ import annotations

import json
import re

from ..config import Settings
from ..metadata import Metadata


def chunk_text(text: str, max_chars: int = 650) -> list[str]:
    """Pack paragraphs into chunks of at most max_chars; split long paragraphs by sentence."""
    pieces: list[str] = []
    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        if len(para) <= max_chars:
            pieces.append(para)
            continue
        cur = ""
        for sent in re.split(r"(?<=[.!?])\s+", para):
            if cur and len(cur) + len(sent) + 1 > max_chars:
                pieces.append(cur)
                cur = sent
            else:
                cur = f"{cur} {sent}".strip()
        if cur:
            pieces.append(cur)
    chunks: list[str] = []
    cur = ""
    for p in pieces:
        if cur and len(cur) + len(p) + 2 > max_chars:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def load_documents(settings: Settings) -> list[dict]:
    with settings.documents_path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def build_chunks(docs: list[dict], meta: Metadata) -> list[dict]:
    out = []
    for d in docs:
        tier = meta.doc_sources[d["source_id"]].tier
        for i, piece in enumerate(chunk_text(d["text"])):
            out.append({
                "id": f"{d['doc_id']}#{i}",
                "text": piece,
                "embed_text": f"{d['title']}. {piece}",
                "metadata": {
                    "doc_id": d["doc_id"],
                    "title": d["title"],
                    "source_id": d["source_id"],
                    "tier": tier,
                    "month": d["month"],
                    "product_ids": "|" + "|".join(d["product_ids"]) + "|" if d["product_ids"] else "",
                    "doc_type": d["doc_type"],
                    "chunk_index": i,
                },
            })
    return out


def build_index(settings: Settings, store, meta: Metadata) -> dict:
    docs = load_documents(settings)
    chunks = build_chunks(docs, meta)
    store.reset()
    store.add_chunks(chunks)
    return {"documents": len(docs), "chunks": len(chunks), "embedder": store.embedder.name}
