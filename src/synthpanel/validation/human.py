"""Compare a synthetic panel with a human Likert survey of the same concepts.

Human data: a CSV with one row per respondent x concept and columns `concept_id`,
`rating` (integer 1..K). Extra columns (demographics) are ignored here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from synthpanel.metrics import correlation_attainment, ks_similarity, mean_rating, ratings_to_pmf
from synthpanel.survey import SurveyResult


def load_human_ratings(path: str | Path) -> dict[str, list[int]]:
    df = pd.read_csv(path, dtype={"concept_id": str})
    missing = {"concept_id", "rating"} - set(df.columns)
    if missing:
        raise ValueError(f"Human ratings file is missing columns: {sorted(missing)}")
    df = df.dropna(subset=["rating"])
    return {cid: grp["rating"].astype(int).tolist() for cid, grp in df.groupby("concept_id")}


def compare_with_humans(result: SurveyResult, human: dict[str, list[int]], n_boot: int = 2000) -> dict:
    synth = result.by_concept().set_index("concept_id")
    rows = []
    for cid, ratings in sorted(human.items()):
        if cid not in synth.index:
            continue
        h_pmf = ratings_to_pmf(ratings, result.n_points)
        s_pmf = synth.loc[cid, result.pmf_columns].to_numpy(dtype=float)
        rows.append({
            "concept_id": cid,
            "n_human": len(ratings),
            "n_synthetic": int(synth.loc[cid, "n"]),
            "mean_human": mean_rating(h_pmf),
            "mean_synthetic": mean_rating(s_pmf),
            "ks_similarity": ks_similarity(s_pmf, h_pmf),
        })
    table = pd.DataFrame(rows)
    if table.empty:
        raise ValueError("No concept_id overlaps between the synthetic and human panels.")
    summary = {
        "n_concepts": len(table),
        "mean_ks_similarity": float(table["ks_similarity"].mean()),
        "median_ks_similarity": float(table["ks_similarity"].median()),
    }
    if len(table) >= 3:
        summary["correlation_attainment"] = correlation_attainment(
            synth["mean_pi"].to_dict(), human, n_boot=n_boot)
    return {"summary": summary, "per_concept": table}


def tune_ssr(responses: pd.DataFrame, human: dict[str, list[int]], scorer_factory,
             temperatures=(0.5, 0.75, 1.0, 1.5, 2.0), epsilons=(0.0, 0.01, 0.05)) -> pd.DataFrame:
    """Grid-search SSR temperature/epsilon on already-collected answers (no new LLM calls).

    `scorer_factory(temperature, epsilon)` must return an SSRScorer. Pick settings on a
    tuning set of concepts and report results on held-out concepts, or the KS figure will
    be optimistic.
    """
    ok = responses[responses["status"] == "ok"]
    out = []
    for t in temperatures:
        for e in epsilons:
            scorer = scorer_factory(t, e)
            pmfs = scorer.score(ok["response"].tolist())
            ks = []
            for cid, idx in ok.groupby("concept_id").indices.items():
                if cid in human:
                    ks.append(ks_similarity(pmfs[idx].mean(axis=0), ratings_to_pmf(human[cid], scorer.n_points)))
            out.append({"temperature": t, "epsilon": e, "mean_ks_similarity": float(np.mean(ks)) if ks else np.nan})
    return pd.DataFrame(out).sort_values("mean_ks_similarity", ascending=False, ignore_index=True)
