"""Evaluation metrics from the paper, plus summaries of a Likert distribution.

- KS similarity: 1 - max |CDF_a - CDF_b| between two Likert distributions (1 = identical).
- Correlation attainment: how close the synthetic panel's concept ranking comes to the best
  ranking a human panel could achieve, given that humans disagree with themselves.

      rho = E[corr(synthetic means, human means)] / E[corr(human half A means, human half B means)]

  The denominator is the human test-retest ceiling, estimated by repeatedly splitting each
  concept's human respondents in two at random. rho near 1 means the synthetic panel ranks
  concepts about as well as a second, independent human panel would. The paper reports
  about 0.9.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
from scipy import stats


def ks_similarity(p: np.ndarray, q: np.ndarray) -> float:
    p = np.asarray(p, float) / np.sum(p)
    q = np.asarray(q, float) / np.sum(q)
    return float(1.0 - np.max(np.abs(np.cumsum(p) - np.cumsum(q))))


def ratings_to_pmf(ratings: Sequence[int], n_points: int = 5) -> np.ndarray:
    counts = np.bincount(np.asarray(ratings, int) - 1, minlength=n_points)[:n_points].astype(float)
    return counts / counts.sum()


def mean_rating(pmf: np.ndarray) -> float:
    return float(np.dot(pmf, np.arange(1, len(pmf) + 1)))


def top_box(pmf: np.ndarray, k: int = 2) -> float:
    """Share in the top k points (top-2-box is the usual purchase-intent headline)."""
    return float(np.sum(pmf[-k:]))


def _corr(x: np.ndarray, y: np.ndarray, method: str) -> float:
    if method == "spearman":
        return float(stats.spearmanr(x, y).statistic)
    return float(stats.pearsonr(x, y).statistic)


def test_retest_ceiling(
    human: Mapping[str, Sequence[int]], n_boot: int = 2000, method: str = "pearson", seed: int = 0
) -> np.ndarray:
    """Bootstrap split-half correlations of human concept means. Returns all draws."""
    rng = np.random.default_rng(seed)
    ids = [c for c, r in human.items() if len(r) >= 4]
    if len(ids) < 3:
        raise ValueError("Need at least 3 concepts with 4+ human ratings each.")
    arrays = [np.asarray(human[c], float) for c in ids]
    out = np.empty(n_boot)
    for b in range(n_boot):
        a_means, b_means = [], []
        for arr in arrays:
            perm = rng.permutation(len(arr))
            half = len(arr) // 2
            a_means.append(arr[perm[:half]].mean())
            b_means.append(arr[perm[half:]].mean())
        out[b] = _corr(np.array(a_means), np.array(b_means), method)
    return out


def correlation_attainment(
    synthetic_means: Mapping[str, float],
    human: Mapping[str, Sequence[int]],
    n_boot: int = 2000,
    method: str = "pearson",
    seed: int = 0,
) -> dict[str, float]:
    """Correlation attainment rho with bootstrap over human respondents.

    Each bootstrap draw resamples every concept's human ratings with replacement, then
    correlates the synthetic concept means with the resampled human means.
    """
    rng = np.random.default_rng(seed)
    ids = [c for c in synthetic_means if c in human and len(human[c]) >= 4]
    if len(ids) < 3:
        raise ValueError("Need at least 3 concepts present in both panels.")
    syn = np.array([synthetic_means[c] for c in ids])
    arrays = [np.asarray(human[c], float) for c in ids]
    rxy = np.empty(n_boot)
    for b in range(n_boot):
        hum = np.array([rng.choice(arr, size=len(arr), replace=True).mean() for arr in arrays])
        rxy[b] = _corr(syn, hum, method)
    rxx = test_retest_ceiling({c: human[c] for c in ids}, n_boot=n_boot, method=method, seed=seed + 1)
    return {
        "rho": float(np.mean(rxy) / np.mean(rxx)),
        "r_synthetic_human": float(np.mean(rxy)),
        "r_test_retest": float(np.mean(rxx)),
        "n_concepts": len(ids),
    }
