"""Text embedders.

Anthropic does not offer an embeddings endpoint, so the embedder is pluggable:

- `VoyageEmbedder`: hosted embeddings from Voyage AI (`pip install synthpanel[voyage]`,
  needs VOYAGE_API_KEY).
- `SentenceTransformerEmbedder`: runs locally, no data leaves the machine
  (`pip install synthpanel[local]`).
- `HashingEmbedder`: deterministic bag-of-words hashing for tests only. It does not
  capture meaning and must not be used for real scoring.

The paper used OpenAI's text-embedding-3-small. SSR results depend on the embedder, so
re-check KS similarity and correlation attainment after switching models.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, Sequence

import numpy as np


class Embedder(Protocol):
    """Anything that maps a list of texts to an (n, d) float array."""

    name: str

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


class CachingEmbedder:
    """Wraps an embedder and memoises results; anchors are embedded once per run."""

    def __init__(self, inner: Embedder):
        self.inner = inner
        self.name = inner.name
        self._cache: dict[str, np.ndarray] = {}

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            vectors = self.inner.embed(missing)
            for text, vec in zip(missing, vectors):
                self._cache[text] = np.asarray(vec, dtype=float)
        return np.vstack([self._cache[t] for t in texts])


class VoyageEmbedder:
    def __init__(self, model: str = "voyage-3.5", batch_size: int = 128):
        import voyageai  # optional dependency

        self._client = voyageai.Client()
        self.model = model
        self.batch_size = batch_size
        self.name = f"voyage:{model}"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = list(texts[i : i + self.batch_size])
            out.extend(self._client.embed(chunk, model=self.model, input_type="document").embeddings)
        return np.asarray(out, dtype=float)


class SentenceTransformerEmbedder:
    def __init__(self, model: str = "sentence-transformers/all-mpnet-base-v2"):
        from sentence_transformers import SentenceTransformer  # optional dependency

        self._model = SentenceTransformer(model)
        self.name = f"st:{model}"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self._model.encode(list(texts), normalize_embeddings=True), dtype=float)


class HashingEmbedder:
    """Test-only embedder: hashed unigrams and bigrams. Not semantically meaningful."""

    def __init__(self, dim: int = 512):
        self.dim = dim
        self.name = f"hashing:{dim}"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        mat = np.zeros((len(texts), self.dim))
        for row, text in enumerate(texts):
            tokens = re.findall(r"[a-z']+", text.lower())
            grams = tokens + [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]
            for g in grams:
                h = int(hashlib.md5(g.encode()).hexdigest(), 16)
                mat[row, h % self.dim] += 1.0 if (h >> 64) % 2 else -1.0
        return mat


def get_embedder(spec: str) -> Embedder:
    """Build an embedder from a spec string: 'voyage[:model]', 'st[:model]' or 'hashing'."""
    kind, _, model = spec.partition(":")
    if kind == "voyage":
        return CachingEmbedder(VoyageEmbedder(model or "voyage-3.5"))
    if kind == "st":
        return CachingEmbedder(SentenceTransformerEmbedder(model or "sentence-transformers/all-mpnet-base-v2"))
    if kind == "hashing":
        return CachingEmbedder(HashingEmbedder())
    raise ValueError(f"Unknown embedder spec {spec!r}; use 'voyage', 'st' or 'hashing'.")
