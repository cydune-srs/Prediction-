import numpy as np
import pytest

from synthpanel.anchors import AnchorSet
from synthpanel.ssr import SSRScorer, similarities_to_pmf


class OneHotEmbedder:
    """Maps each known sentence to a fixed vector so similarities are exact."""

    name = "onehot"

    def __init__(self, table):
        self.table = table

    def embed(self, texts):
        return np.array([self.table[t] for t in texts], dtype=float)


def test_pmf_subtracts_minimum_and_normalises():
    pmf = similarities_to_pmf(np.array([[0.70, 0.75, 0.80, 0.85, 0.90]]))
    np.testing.assert_allclose(pmf, [[0.0, 0.1, 0.2, 0.3, 0.4]])


def test_epsilon_gives_mass_to_least_similar_point():
    pmf = similarities_to_pmf(np.array([[0.70, 0.75, 0.80, 0.85, 0.90]]), epsilon=0.5)
    assert pmf[0, 0] > 0
    assert pmf.sum() == pytest.approx(1.0)
    # Shifted sims sum to 0.5; eps goes on the argmin and the denominator: (0 + 0.5) / (0.5 + 0.5).
    assert pmf[0, 0] == pytest.approx(0.5)
    assert pmf[0, -1] == pytest.approx(0.2 / 1.0)


def test_temperature_sharpens_and_flattens():
    sims = np.array([[0.70, 0.75, 0.80, 0.85, 0.90]])
    base = similarities_to_pmf(sims)
    sharp = similarities_to_pmf(sims, temperature=0.5)
    flat = similarities_to_pmf(sims, temperature=3.0)
    assert sharp[0, -1] > base[0, -1] > flat[0, -1]
    for p in (sharp, flat):
        assert p.sum() == pytest.approx(1.0)


def test_equal_similarities_give_uniform():
    np.testing.assert_allclose(similarities_to_pmf(np.full((1, 5), 0.8)), np.full((1, 5), 0.2))


def test_scorer_puts_most_mass_on_matching_anchor():
    anchors = [AnchorSet(statements=("no", "maybe", "yes"))]
    table = {"no": [1, 0, 0], "maybe": [0, 1, 0], "yes": [0, 0, 1],
             "sure, I'd buy it": [0.1, 0.3, 0.95], "not for me": [0.95, 0.3, 0.1]}
    scorer = SSRScorer(OneHotEmbedder(table), anchors)
    pmfs = scorer.score(["sure, I'd buy it", "not for me"])
    assert pmfs.shape == (2, 3)
    assert pmfs[0].argmax() == 2 and pmfs[1].argmax() == 0
    exp = scorer.expected_rating(pmfs)
    assert exp[0] > 2 > exp[1]


def test_scorer_averages_across_anchor_sets():
    anchors = [AnchorSet(statements=("a1", "a2")), AnchorSet(statements=("b1", "b2"))]
    table = {"a1": [1, 0], "a2": [0, 1], "b1": [0, 1], "b2": [1, 0], "r": [0.2, 1.0]}
    pmf = SSRScorer(OneHotEmbedder(table), anchors).score(["r"])[0]
    # Set a says point 2, set b says point 1, equally strongly: the mean is uniform.
    np.testing.assert_allclose(pmf, [0.5, 0.5])


def test_mismatched_anchor_sizes_rejected():
    table = {k: [1.0] for k in ("a", "b", "c", "d", "e")}
    with pytest.raises(ValueError):
        SSRScorer(OneHotEmbedder(table), [AnchorSet(statements=("a", "b")), AnchorSet(statements=("c", "d", "e"))])
