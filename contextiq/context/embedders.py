"""Embedders. The hashing embedder is deterministic and needs no downloads; the
sentence-transformers embedder is the recommended one for real use."""
from __future__ import annotations

import hashlib
import math
import re
import warnings
from collections import Counter

_STOP = {
    "a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "with", "as", "at", "by", "from", "we", "our", "should", "do", "did", "why",
    "what", "which", "how", "can", "will", "than", "then", "there", "their", "they", "has", "have", "had",
}


def _stem(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 4 and tok.endswith("ing"):
        return tok[:-3]
    if len(tok) > 3 and tok.endswith("ed"):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


class HashingEmbedder:
    """Feature-hashed bag of stemmed unigrams and bigrams, L2-normalised."""

    name = "hash"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _bucket(self, feature: str) -> int:
        h = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        return int.from_bytes(h, "big") % self.dim

    def _embed_one(self, text: str) -> list[float]:
        toks = [_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP]
        feats = Counter(toks)
        feats.update(f"{a}_{b}" for a, b in zip(toks, toks[1:]))
        vec = [0.0] * self.dim
        for f, tf in feats.items():
            w = (1.0 + math.log(tf)) * (0.6 if "_" in f else 1.0)
            vec[self._bucket(f)] += w
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class SentenceTransformerEmbedder:
    name = "st-minilm"
    MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # lazy import

        self._model = SentenceTransformer(self.MODEL)
        self.dim = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


def get_embedder(kind: str = "auto"):
    """kind: 'hash' | 'st' | 'auto' (try the real model, fall back to hashing)."""
    kind = (kind or "auto").lower()
    if kind == "hash":
        return HashingEmbedder()
    if kind == "st":
        return SentenceTransformerEmbedder()
    try:
        return SentenceTransformerEmbedder()
    except Exception as exc:  # noqa: BLE001 - any failure means "fall back"
        warnings.warn(f"sentence-transformers unavailable ({type(exc).__name__}); using hashing embedder")
        return HashingEmbedder()
