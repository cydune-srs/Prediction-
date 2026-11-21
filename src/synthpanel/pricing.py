"""Price-test read-outs: compare each cell of a panel with its control cell.

Two lenses, reported side by side:

- **Stated choice.** Each respondent's stated plan (e.g. Black Card / Classic / Not joining)
  is valued at that cell's monthly price, giving revenue per respondent. Because every
  persona answers every cell, the difference to control is computed within persona and its
  95% interval comes from the spread of those paired differences.
- **SSR intent.** The paper's method: mean and top-2-box of the Likert distribution
  recovered from the free-text answer. Stated choices from LLMs (like direct ratings) tend to
  be overconfident, so treat choice shares as directional and use the intent shift as a
  cross-check on the direction and size of the effect.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from synthpanel.study import Panel
from synthpanel.survey import SurveyResult


def respondent_revenue(result: SurveyResult, panel: Panel) -> pd.DataFrame:
    df = result.responses[(result.responses["status"] == "ok")].copy()
    df["revenue"] = [panel.revenue(c).get(ch, np.nan) for c, ch in zip(df["concept_id"], df["choice"])]
    return df


def price_test_readout(result: SurveyResult, panel: Panel) -> pd.DataFrame:
    df = respondent_revenue(result, panel)
    base = df[df["concept_id"] == panel.control].set_index("persona_id")
    rows = []
    for cell in panel.cells:
        cur = df[df["concept_id"] == cell.concept_id].set_index("persona_id")
        row = {
            "cell": cell.concept_id,
            "n": len(cur),
            "mean_intent": float(cur["expected_rating"].mean()),
            "top2box_intent": float(cur[result.pmf_columns[-2:]].sum(axis=1).mean()),
            "revenue_per_respondent": float(cur["revenue"].mean()),
        }
        for option in (panel.spec.choice.options if panel.spec.choice else ()):
            row[f"share:{option}"] = float((cur["choice"] == option).mean())
        paired = cur[["revenue", "expected_rating"]].merge(
            base[["revenue", "expected_rating"]], left_index=True, right_index=True, suffixes=("", "_ctl")).dropna()
        if cell.concept_id != panel.control and len(paired) > 1:
            d_rev = paired["revenue"] - paired["revenue_ctl"]
            d_int = paired["expected_rating"] - paired["expected_rating_ctl"]
            half = 1.96 * d_rev.std(ddof=1) / np.sqrt(len(d_rev))
            ctl = paired["revenue_ctl"].mean()
            row.update({
                "d_revenue": float(d_rev.mean()),
                "d_revenue_ci95": (float(d_rev.mean() - half), float(d_rev.mean() + half)),
                "d_revenue_pct": float(d_rev.mean() / ctl) if ctl else np.nan,
                "d_intent": float(d_int.mean()),
                "d_intent_ci95": (float(d_int.mean() - 1.96 * d_int.std(ddof=1) / np.sqrt(len(d_int))),
                                  float(d_int.mean() + 1.96 * d_int.std(ddof=1) / np.sqrt(len(d_int)))),
            })
        rows.append(row)
    return pd.DataFrame(rows)


def switching_matrix(result: SurveyResult, panel: Panel, cell: str) -> pd.DataFrame:
    """Rows: choice under control; columns: choice under `cell` (same personas)."""
    df = result.responses[result.responses["status"] == "ok"]
    a = df[df["concept_id"] == panel.control].set_index("persona_id")["choice"]
    b = df[df["concept_id"] == cell].set_index("persona_id")["choice"]
    joined = pd.concat([a.rename("control"), b.rename(cell)], axis=1, join="inner")
    return pd.crosstab(joined["control"], joined[cell])
