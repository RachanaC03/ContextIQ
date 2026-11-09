from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AS_OF = "2026-11-15"  # the synthetic "today": "last month" resolves to 2026-10


@dataclass
class Settings:
    context_dir: Path = ROOT / "data" / "context"
    generated_dir: Path = ROOT / "data" / "generated"
    embedder: str = field(default_factory=lambda: os.getenv("EMBEDDER", "auto"))
    as_of: str = AS_OF
    seed: int = 42

    def __post_init__(self) -> None:
        self.context_dir = Path(self.context_dir)
        self.generated_dir = Path(self.generated_dir)

    @property
    def db_path(self) -> Path:
        return self.generated_dir / "hearthline.db"

    @property
    def documents_path(self) -> Path:
        return self.generated_dir / "documents.jsonl"

    @property
    def ground_truth_path(self) -> Path:
        return self.generated_dir / "ground_truth.json"

    @property
    def chroma_dir(self) -> Path:
        return self.generated_dir / "chroma"

    @property
    def audit_path(self) -> Path:
        return self.generated_dir / "audit.db"

    def ensure_dirs(self) -> None:
        self.generated_dir.mkdir(parents=True, exist_ok=True)
