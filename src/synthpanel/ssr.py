"""Semantic Similarity Rating: free text -> probability distribution over Likert points.

For a response embedding t and anchor embeddings a_1..a_K (one anchor set):

    s_r    = cos(a_r, t)
    p(r)   = (s_r - min_k s_k + eps * [r == argmin_k s_k]) / (sum_k (s_k - min_j s_j) + eps)
    p_T(r) ∝ p(r) ** (1 / T)

Subtracting the minimum similarity removes the large shared component that cosine
similarities between short sentences always have; `eps` keeps the least-similar point from
being forced to exactly zero, and the temperature T sharpens (T < 1) or flattens (T > 1)
the distribution. The final distribution is the mean across anchor sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from synthpanel.anchors import DEFAULT_PURCHASE_INTENT_ANCHORS, AnchorSet
from synthpanel.embeddings import Embedder


def _unit(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=-1, keepdims=True)
    return mat / np.where(norms == 0, 1.0, norms)


def similarities_to_pmf(sims: np.ndarray, epsilon: float = 0.0, temperature: float = 1.0) -> np.ndarray:
    """Map an (n, K) array of cosine similarities to (n, K) probability mass functions."""
    sims = np.atleast_2d(np.asarray(sims, dtype=float))
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    shifted = sims - sims.min(axis=1, keepdims=True)
    if epsilon:
        shifted[np.arange(len(sims)), sims.argmin(axis=1)] += epsilon
    totals = shifted.sum(axis=1, keepdims=True)
    # A response equidistant from every anchor carries no information: return uniform.
    pmf = np.where(totals > 0, shifted / np.where(totals > 0, totals, 1.0), 1.0 / sims.shape[1])
    if temperature != 1.0:
        pmf = pmf ** (1.0 / temperature)
        pmf /= pmf.sum(axis=1, keepdims=True)
    return pmf


@dataclass
class SSRScorer:
    embedder: Embedder
    anchor_sets: Sequence[AnchorSet] = field(default_factory=lambda: DEFAULT_PURCHASE_INTENT_ANCHORS)
    epsilon: float = 0.0
    temperature: float = 1.0

    def __post_init__(self) -> None:
        sizes = {a.n_points for a in self.anchor_sets}
        if len(sizes) != 1:
            raise ValueError("All anchor sets must have the same number of Likert points.")
        self.n_points = sizes.pop()
        flat = [s for a in self.anchor_sets for s in a.statements]
        emb = _unit(self.embedder.embed(flat))
        self._anchor_emb = emb.reshape(len(self.anchor_sets), self.n_points, -1)  # (M, K, d)

    @property
    def scale(self) -> np.ndarray:
        return np.arange(1, self.n_points + 1, dtype=float)

    def score(self, responses: Sequence[str]) -> np.ndarray:
        """Return an (n, K) array: one Likert distribution per response."""
        if not responses:
            return np.empty((0, self.n_points))
        resp = _unit(self.embedder.embed(list(responses)))  # (n, d)
        sims = np.einsum("mkd,nd->mnk", self._anchor_emb, resp)  # (M, n, K)
        pmfs = np.stack([similarities_to_pmf(s, self.epsilon, self.temperature) for s in sims])
        return pmfs.mean(axis=0)

    def expected_rating(self, pmfs: np.ndarray) -> np.ndarray:
        return pmfs @ self.scale
