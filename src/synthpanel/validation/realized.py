"""Backtest synthetic purchase intent against realized purchases.

Purchase intent is a stated, relative measure. Realized sales also depend on distribution,
price, marketing and awareness, so this module:

1. Measures rank agreement (Spearman) between a synthetic PI statistic and a realized
   outcome across concepts, with a bootstrap confidence interval over concepts.
2. Optionally does the same within groups (e.g. category), where those confounders are
   more comparable. Within-group agreement is the more honest test.
3. Fits a small calibration, outcome ~ a + b * PI (optionally on log outcome), and reports
   leave-one-out error, so PI can be turned into a sales or share forecast with an error
   band.

Outcomes table: one row per concept with `concept_id` and the outcome column, e.g. net
sales in the first N weeks after launch, a brand's share of category sales, or Y/Y growth
over the next quarter. Build it from card/receipt panels or reported KPIs; see `sources`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


def _spearman_ci(x: np.ndarray, y: np.ndarray, n_boot: int, seed: int) -> tuple[float, float, float, float]:
    rho, pval = stats.spearmanr(x, y)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(x), len(x))
        if len(np.unique(idx)) < 3:
            continue
        r = stats.spearmanr(x[idx], y[idx]).statistic
        if np.isfinite(r):
            boots.append(r)
    lo, hi = (np.percentile(boots, [2.5, 97.5]) if boots else (np.nan, np.nan))
    return float(rho), float(pval), float(lo), float(hi)


@dataclass
class Calibration:
    intercept: float
    slope: float
    log_outcome: bool
    loo_mae: float
    loo_mape: float
    residual_sd: float

    def predict(self, pi: np.ndarray | float) -> np.ndarray:
        z = self.intercept + self.slope * np.asarray(pi, float)
        return np.exp(z) if self.log_outcome else z


def fit_calibration(pi: np.ndarray, outcome: np.ndarray, log_outcome: bool = True) -> Calibration:
    pi = np.asarray(pi, float)
    outcome = np.asarray(outcome, float)
    if log_outcome and np.any(outcome <= 0):
        raise ValueError("log_outcome requires strictly positive outcomes (use growth or share without log).")
    y = np.log(outcome) if log_outcome else outcome
    fit = stats.linregress(pi, y)
    loo = np.empty_like(y)
    for i in range(len(y)):
        mask = np.arange(len(y)) != i
        f = stats.linregress(pi[mask], y[mask])
        loo[i] = f.intercept + f.slope * pi[i]
    pred = np.exp(loo) if log_outcome else loo
    err = pred - outcome
    with np.errstate(divide="ignore", invalid="ignore"):
        mape = float(np.nanmean(np.abs(err / outcome)))
    return Calibration(float(fit.intercept), float(fit.slope), log_outcome,
                       float(np.mean(np.abs(err))), mape, float(np.std(y - (fit.intercept + fit.slope * pi), ddof=2)))


def backtest(
    concept_summary: pd.DataFrame,
    outcomes: pd.DataFrame,
    outcome_col: str,
    pi_col: str = "top2box",
    group_col: str | None = None,
    log_outcome: bool = True,
    n_boot: int = 2000,
    seed: int = 0,
) -> dict:
    """Join synthetic PI with realized outcomes on concept_id and score the agreement."""
    df = concept_summary[["concept_id", pi_col]].merge(outcomes, on="concept_id", how="inner").dropna(
        subset=[pi_col, outcome_col])
    if len(df) < 5:
        raise ValueError(f"Only {len(df)} concepts have both synthetic PI and an outcome; need at least 5.")
    x, y = df[pi_col].to_numpy(float), df[outcome_col].to_numpy(float)
    rho, pval, lo, hi = _spearman_ci(x, y, n_boot, seed)
    report = {
        "n_concepts": len(df),
        "pi_statistic": pi_col,
        "outcome": outcome_col,
        "spearman": rho,
        "spearman_p": pval,
        "spearman_ci95": (lo, hi),
    }
    if group_col:
        groups = []
        for g, sub in df.groupby(group_col):
            if len(sub) >= 5:
                r, p, glo, ghi = _spearman_ci(sub[pi_col].to_numpy(float), sub[outcome_col].to_numpy(float), n_boot, seed)
                groups.append({group_col: g, "n": len(sub), "spearman": r, "p": p, "ci_lo": glo, "ci_hi": ghi})
        report["within_group"] = pd.DataFrame(groups)
    try:
        report["calibration"] = fit_calibration(x, y, log_outcome=log_outcome)
    except ValueError as e:
        report["calibration_error"] = str(e)
    report["joined"] = df
    return report
