from __future__ import annotations

import hashlib
from typing import List


class FakeEmbedder:
    """Deterministic embedder for tests (sha256-based)."""

    def __init__(self, dims: int = 8):
        self.dims = dims

    def embed(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = []
        for i in range(self.dims):
            byte = digest[i]
            values.append((byte / 255.0) * 2 - 1)
        return values

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(text) for text in texts]
