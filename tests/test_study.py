from pathlib import Path

import numpy as np
import pytest

from synthpanel.backends import cortex
from synthpanel.choices import UNPARSED, split_choice
from synthpanel.embeddings import get_embedder
from synthpanel.pricing import price_test_readout, switching_matrix
from synthpanel.prompts import ChoiceSpec, user_text
from synthpanel.respondents import ScriptedRespondent
from synthpanel.ssr import SSRScorer
from synthpanel.study import load_study
from synthpanel.survey import run_survey

PF = Path(__file__).parent.parent / "studies" / "planet_fitness_black_card.yaml"
SPEC = ChoiceSpec("PLAN", ("Black Card", "Classic", "Not joining"))


@pytest.mark.parametrize("text,choice", [
    ("Sounds fine.\n\nPLAN: Classic", "Classic"),
    ("Sounds fine.\n**PLAN:** Black Card.", "Black Card"),
    ("No.\nplan: not joining", "Not joining"),
    ("I'd go with Classic.", UNPARSED),
    ("PLAN: Black Card\nActually no.\nPLAN: Classic", "Classic"),  # last line wins
    ("Hmm.\nPLAN: maybe later", UNPARSED),
])
def test_split_choice(text, choice):
    clean, got = split_choice(text, SPEC)
    assert got == choice
    assert "PLAN" not in clean.upper() or got == UNPARSED


def test_parse_answer_scores_intent_line():
    from synthpanel.choices import parse_answer
    spec = load_study(PF).panels["prospects"].spec
    text = ("I'd go Classic, the extras aren't for me.\n\n"
            "LIKELIHOOD: I'm very likely to join.\n**PLAN:** Classic")
    clean, to_score, choice = parse_answer(text, spec)
    assert clean == "I'd go Classic, the extras aren't for me."
    assert to_score == "I'm very likely to join." and choice == "Classic"
    # Without an intent line, SSR falls back to the answer itself.
    clean, to_score, choice = parse_answer("Not for me.\nPLAN: Not joining", spec)
    assert to_score == clean == "Not for me." and choice == "Not joining"


def test_instructions_list_both_lines():
    spec = load_study(PF).panels["prospects"].spec
    tail = spec.tail()
    assert "add these final lines" in tail
    assert tail.index("LIKELIHOOD:") < tail.index("PLAN: <one of: Black Card | Classic | Not joining>")


def test_study_loads_and_validates():
    study = load_study(PF)
    assert set(study.panels) == {"prospects", "members"}
    p = study.panels["prospects"]
    assert p.control == "A0_bc2499" and len(p.cells) == 4
    assert p.revenue("A1_bc2799") == {"Black Card": 27.99, "Classic": 15.0, "Not joining": 0.0}
    assert all(a.n_points == 5 for a in p.anchors)
    assert "$27.99" in p.cell("A1_bc2799").as_text() and "$24.99" not in p.cell("A1_bc2799").as_text()


def test_sql_prompt_matches_python_prompt():
    study = load_study(PF)
    for panel in study.panels.values():
        persona = panel.personas()[0]
        cell = panel.cells[1]
        values = {**persona.attributes, "__stimulus__": cell.as_text()}
        assert cortex.render_parts(cortex.prompt_parts(panel), values) == user_text(cell, persona, panel.spec)


def test_cortex_sql_builds():
    study = load_study(PF)
    stage = "@DB.SCHEMA.STAGE/run1"
    panel = study.panels["prospects"]
    sql = cortex.personas_sql(panel, stage)
    assert "GENERATOR(ROWCOUNT => 300)" in sql and "RANDOM(11001)" in sql
    sql = cortex.answers_sql(study, panel, "A1_bc2799", stage, max_personas=5)
    assert "TRY_COMPLETE($$claude-opus-4-6$$" in sql and "prospects-0005" in sql
    sql = cortex.score_sql(study, panel, stage)
    assert sql.count("EMBED_TEXT_1024") == 2 and "PLAN" in sql
    assert "WHEN cell = $$A2_bc2999$$ AND choice = $$Black Card$$ THEN 29.99" in cortex.readout_sql(panel, stage)
    assert "cell <> $$A0_bc2499$$" in cortex.paired_sql(panel, stage)
    with pytest.raises(ValueError):
        cortex.lit("no $$ allowed")


def test_price_readout_paired_deltas():
    study = load_study(PF)
    panel = study.panels["prospects"]
    personas = panel.personas()[:40]

    def script(task):
        # Price-sensitive half switches to Classic at $27.99+; the rest keep Black Card.
        sensitive = int(task.persona.persona_id.split("-")[1]) % 2 == 0
        if task.concept.concept_id in ("A1_bc2799", "A2_bc2999") and sensitive:
            return "Too pricey for the extras, I'd take the cheaper one.\nPLAN: Classic"
        return "I'd definitely sign up for the full membership.\nPLAN: Black Card"

    result = run_survey(panel.cells, personas, ScriptedRespondent(script),
                        SSRScorer(get_embedder("hashing"), panel.anchors), spec=panel.spec)
    out = price_test_readout(result, panel).set_index("cell")
    assert out.loc["A0_bc2499", "share:Black Card"] == 1.0
    assert out.loc["A1_bc2799", "share:Classic"] == pytest.approx(0.5)
    # Revenue per respondent at $27.99: half at 27.99, half at 15.
    assert out.loc["A1_bc2799", "revenue_per_respondent"] == pytest.approx((27.99 + 15) / 2)
    assert out.loc["A1_bc2799", "d_revenue"] == pytest.approx((27.99 + 15) / 2 - 24.99)
    lo, hi = out.loc["A1_bc2799", "d_revenue_ci95"]
    assert lo < out.loc["A1_bc2799", "d_revenue"] < hi
    assert np.isnan(out.loc["A0_bc2499", "d_revenue"]) if "d_revenue" in out else True
    m = switching_matrix(result, panel, "A1_bc2799")
    assert m.loc["Black Card", "Classic"] == 20
