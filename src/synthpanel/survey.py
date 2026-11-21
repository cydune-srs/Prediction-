"""Run a synthetic survey and aggregate it."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from synthpanel.choices import parse_answer
from synthpanel.concepts import Concept
from synthpanel.metrics import mean_rating, top_box
from synthpanel.personas import Persona
from synthpanel.prompts import SurveySpec
from synthpanel.respondents import Respondent, Task
from synthpanel.ssr import SSRScorer

log = logging.getLogger(__name__)


@dataclass
class SurveyResult:
    responses: pd.DataFrame  # one row per answer, with p1..pK, expected_rating and (optionally) choice
    n_points: int

    @property
    def pmf_columns(self) -> list[str]:
        return [f"p{k}" for k in range(1, self.n_points + 1)]

    def _summarise(self, group_cols: list[str]) -> pd.DataFrame:
        ok = self.responses[self.responses["status"] == "ok"]
        has_choice = "choice" in ok.columns and ok["choice"].astype(str).str.len().gt(0).any()
        rows = []
        for keys, grp in ok.groupby(group_cols, sort=True):
            # Panel distribution = mean of individual SSR distributions.
            pmf = grp[self.pmf_columns].to_numpy().mean(axis=0)
            keys = keys if isinstance(keys, tuple) else (keys,)
            row = {
                **dict(zip(group_cols, keys)),
                "n": len(grp),
                "mean_pi": mean_rating(pmf),
                "top2box": top_box(pmf, 2),
                **{c: v for c, v in zip(self.pmf_columns, pmf)},
            }
            if has_choice:
                shares = grp["choice"].value_counts(normalize=True)
                row.update({f"choice:{k}": float(v) for k, v in shares.items()})
            rows.append(row)
        out = pd.DataFrame(rows).fillna({c: 0.0 for c in pd.DataFrame(rows).columns if c.startswith("choice:")})
        status = self.responses.groupby(group_cols)["status"].value_counts().unstack(fill_value=0)
        for col in ("refused", "error"):
            if col in status:
                out = out.merge(status[[col]].rename(columns={col: f"n_{col}"}).reset_index(), on=group_cols, how="left")
        return out

    def by_concept(self) -> pd.DataFrame:
        return self._summarise(["concept_id"]).sort_values("mean_pi", ascending=False, ignore_index=True)

    def by_segment(self, attribute: str) -> pd.DataFrame:
        return self._summarise(["concept_id", attribute])

    def save(self, folder: str | Path) -> None:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        self.responses.to_csv(folder / "responses.csv", index=False)
        self.by_concept().to_csv(folder / "concepts.csv", index=False)
        (folder / "meta.json").write_text(json.dumps({"n_points": self.n_points}))

    @classmethod
    def load(cls, folder: str | Path) -> "SurveyResult":
        folder = Path(folder)
        meta = json.loads((folder / "meta.json").read_text())
        return cls(pd.read_csv(folder / "responses.csv", keep_default_na=False,
                               dtype={"concept_id": str, "persona_id": str}), meta["n_points"])


def run_survey(
    concepts: Sequence[Concept],
    personas: Sequence[Persona],
    respondent: Respondent,
    scorer: SSRScorer,
    draws_per_persona: int = 1,
    spec: SurveySpec | None = None,
) -> SurveyResult:
    """Every persona answers every concept `draws_per_persona` times; answers are SSR-scored.

    Each call is independent, so using the same personas for every concept is a paired
    (within-subject) design without carry-over: no respondent sees another concept.
    If `spec.choice` is set, the stated-choice line is parsed into a `choice` column. If
    `spec.intent` is set, SSR scores only the intent line (falling back to the answer).
    """
    tasks = [Task(c, p, d) for c in concepts for p in personas for d in range(draws_per_persona)]
    log.info("Running %d tasks (%d concepts x %d personas x %d draws)",
             len(tasks), len(concepts), len(personas), draws_per_persona)
    answers = respondent.answer(tasks)

    texts, scored, choices = [], [], []
    for a in answers:
        if spec and a.status == "ok":
            text, to_score, choice = parse_answer(a.text, spec)
        else:
            text, to_score, choice = a.text, a.text, ""
        texts.append(text)
        scored.append(to_score)
        choices.append(choice)

    ok_idx = [i for i, a in enumerate(answers) if a.status == "ok" and scored[i]]
    pmfs = np.full((len(tasks), scorer.n_points), np.nan)
    if ok_idx:
        pmfs[ok_idx] = scorer.score([scored[i] for i in ok_idx])

    rows = []
    for i, (task, ans, pmf) in enumerate(zip(tasks, answers, pmfs)):
        status = ans.status if (ans.status != "ok" or scored[i]) else "error"
        rows.append({
            "concept_id": task.concept.concept_id,
            "persona_id": task.persona.persona_id,
            "draw": task.draw,
            **dict(task.persona.attributes),
            "status": status,
            "model": ans.model,
            "detail": ans.detail,
            "response": texts[i],
            "scored_text": scored[i],
            "choice": choices[i],
            **{f"p{k + 1}": v for k, v in enumerate(pmf)},
            "expected_rating": float(pmf @ scorer.scale) if status == "ok" else np.nan,
        })
    failed = len(tasks) - len(ok_idx)
    if failed:
        log.warning("%d of %d answers were refused or failed; they are excluded from aggregates.", failed, len(tasks))
    return SurveyResult(pd.DataFrame(rows), scorer.n_points)
