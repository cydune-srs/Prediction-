import numpy as np
import pandas as pd
import pytest

from synthpanel.concepts import Concept, load_concepts
from synthpanel.embeddings import get_embedder
from synthpanel.personas import Persona, PersonaSampler, load_personas
from synthpanel.prompts import user_content
from synthpanel.respondents import Answer, ScriptedRespondent
from synthpanel.ssr import SSRScorer
from synthpanel.survey import SurveyResult, run_survey
from synthpanel.validation.human import compare_with_humans
from synthpanel.validation.realized import backtest

LIKES = {"good": "I definitely would buy this.", "bad": "I definitely would not buy this."}


def _concepts():
    return [Concept("good", "Good thing", "A product people like."),
            Concept("bad", "Bad thing", "A product people dislike.")]


def test_sampler_is_reproducible_and_matches_marginals():
    a = PersonaSampler(seed=3).sample(2000)
    b = PersonaSampler(seed=3).sample(2000)
    assert [p.attributes for p in a[:20]] == [p.attributes for p in b[:20]]
    share_65 = np.mean([p.attributes["age"] == "65+" for p in a])
    assert share_65 == pytest.approx(0.23, abs=0.03)


def test_prompt_puts_concept_before_persona():
    persona = Persona("p1", {"age": "35-44", "gender": "woman"})
    blocks = user_content(_concepts()[0], persona)
    assert "Good thing" in blocks[0]["text"] and "Age: 35-44" in blocks[1]["text"]
    assert "How likely" in blocks[1]["text"]


def test_survey_ranks_concepts_and_excludes_failures():
    personas = PersonaSampler(seed=0).sample(20)

    class Flaky(ScriptedRespondent):
        def answer(self, tasks):
            out = super().answer(tasks)
            out[0] = Answer(out[0].task_id, "", "refused", detail="refusal")
            return out

    scorer = SSRScorer(get_embedder("hashing"))
    result = run_survey(_concepts(), personas, Flaky(lambda t: LIKES[t.concept.concept_id]), scorer)
    summary = result.by_concept().set_index("concept_id")
    assert summary.loc["good", "mean_pi"] > summary.loc["bad", "mean_pi"]
    assert summary.loc["good", "n"] + summary.loc["bad", "n"] == 39
    assert summary["n_refused"].sum() == 1
    seg = result.by_segment("gender")
    assert set(seg.columns) >= {"concept_id", "gender", "mean_pi"}


def test_save_and_load_roundtrip(tmp_path):
    scorer = SSRScorer(get_embedder("hashing"))
    result = run_survey(_concepts(), PersonaSampler().sample(5), ScriptedRespondent(lambda t: LIKES[t.concept.concept_id]), scorer)
    result.save(tmp_path)
    loaded = SurveyResult.load(tmp_path)
    pd.testing.assert_frame_equal(loaded.by_concept(), result.by_concept(), check_dtype=False)


def test_compare_with_humans_runs():
    concepts = [Concept(f"c{i}", f"C{i}", "x") for i in range(4)]
    texts = ["I definitely would not buy this.", "I probably would not buy this.",
             "I probably would buy this.", "I definitely would buy this."]
    scorer = SSRScorer(get_embedder("hashing"))
    result = run_survey(concepts, PersonaSampler().sample(10),
                        ScriptedRespondent(lambda t: texts[int(t.concept.concept_id[1])]), scorer)
    rng = np.random.default_rng(0)
    human = {f"c{i}": np.clip(np.round(rng.normal(1.5 + i, 0.8, 60)), 1, 5).astype(int).tolist() for i in range(4)}
    report = compare_with_humans(result, human, n_boot=200)
    assert report["summary"]["n_concepts"] == 4
    assert report["summary"]["correlation_attainment"]["r_synthetic_human"] > 0.5


def test_backtest_recovers_monotone_relationship():
    rng = np.random.default_rng(0)
    pi = np.linspace(0.1, 0.7, 30)
    summary = pd.DataFrame({"concept_id": [f"c{i}" for i in range(30)], "top2box": pi})
    sales = np.exp(10 + 4 * pi + rng.normal(0, 0.15, 30))
    outcomes = pd.DataFrame({"concept_id": summary["concept_id"], "sales": sales,
                             "category": ["a", "b"] * 15})
    rep = backtest(summary, outcomes, "sales", group_col="category", n_boot=300)
    assert rep["spearman"] > 0.8
    assert rep["calibration"].slope == pytest.approx(4, abs=0.5)
    assert rep["calibration"].loo_mape < 0.25
    assert len(rep["within_group"]) == 2


def test_backtest_needs_overlap():
    with pytest.raises(ValueError):
        backtest(pd.DataFrame({"concept_id": ["a"], "top2box": [0.3]}),
                 pd.DataFrame({"concept_id": ["a"], "y": [1.0]}), "y")


def test_loaders(tmp_path):
    (tmp_path / "c.yaml").write_text("- {concept_id: 1, name: N, description: D, launch_week: 3}\n")
    c = load_concepts(tmp_path / "c.yaml")[0]
    assert c.concept_id == "1" and c.metadata == {"launch_week": 3}
    (tmp_path / "p.csv").write_text("persona_id,age,pets\nx,30,dog\n")
    p = load_personas(tmp_path / "p.csv")[0]
    assert p.persona_id == "x" and "Pets: dog" in p.describe()
