import numpy as np
import pytest

from synthpanel.metrics import (
    correlation_attainment,
    ks_similarity,
    mean_rating,
    ratings_to_pmf,
    test_retest_ceiling as retest_ceiling,
    top_box,
)


def test_ks_similarity_bounds():
    p = np.array([0.1, 0.2, 0.4, 0.2, 0.1])
    assert ks_similarity(p, p) == pytest.approx(1.0)
    assert ks_similarity([1, 0, 0, 0, 0], [0, 0, 0, 0, 1]) == pytest.approx(0.0)


def test_pmf_summaries():
    pmf = ratings_to_pmf([1, 2, 5, 5])
    np.testing.assert_allclose(pmf, [0.25, 0.25, 0, 0, 0.5])
    assert mean_rating(pmf) == pytest.approx(3.25)
    assert top_box(pmf) == pytest.approx(0.5)


def _human_panel(true_means, n=200, seed=0):
    rng = np.random.default_rng(seed)
    return {f"c{i}": np.clip(np.round(rng.normal(m, 1.0, n)), 1, 5).astype(int).tolist()
            for i, m in enumerate(true_means)}


def test_attainment_near_one_when_synthetic_tracks_truth():
    true_means = np.linspace(2.0, 4.0, 12)
    human = _human_panel(true_means)
    syn = {f"c{i}": m for i, m in enumerate(true_means)}
    res = correlation_attainment(syn, human, n_boot=300)
    assert res["r_test_retest"] > 0.8
    assert res["rho"] > 0.9


def test_attainment_low_for_random_synthetic():
    true_means = np.linspace(2.0, 4.0, 12)
    human = _human_panel(true_means)
    rng = np.random.default_rng(1)
    syn = {f"c{i}": v for i, v in enumerate(rng.permutation(true_means))}
    assert correlation_attainment(syn, human, n_boot=300)["rho"] < 0.6


def test_retest_requires_enough_data():
    with pytest.raises(ValueError):
        retest_ceiling({"a": [1, 2, 3, 4], "b": [1, 2]})
