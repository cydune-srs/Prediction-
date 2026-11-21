"""Synthetic respondents' demographic profiles.

Two ways to get a panel:

1. `load_personas(csv)`: one row per respondent with your own attributes. Use this when you
   have a real target-customer profile (a brand's buyer demographics, a panel export).
2. `PersonaSampler`: draws respondents from marginal distributions. The default
   `US_ADULT_MARGINALS` are rounded approximations of US adult population shares and are
   only a starting point; replace them with ACS figures or the target company's customer
   mix. Attributes are drawn independently, so joint structure (e.g. age x income) is lost
   unless you supply personas directly.

The paper found that conditioning on demographics, especially age and income, was needed
to reproduce how purchase intent varies across consumer segments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

US_ADULT_MARGINALS: dict[str, dict[str, float]] = {
    "age": {"18-24": 0.12, "25-34": 0.17, "35-44": 0.17, "45-54": 0.15, "55-64": 0.16, "65+": 0.23},
    "gender": {"woman": 0.51, "man": 0.49},
    "household_income": {
        "under $25,000": 0.17,
        "$25,000-$49,999": 0.19,
        "$50,000-$74,999": 0.16,
        "$75,000-$99,999": 0.12,
        "$100,000-$149,999": 0.16,
        "$150,000 or more": 0.20,
    },
    "region": {"Northeast": 0.17, "Midwest": 0.21, "South": 0.38, "West": 0.24},
    "race_ethnicity": {
        "White": 0.58,
        "Hispanic or Latino": 0.18,
        "Black or African American": 0.12,
        "Asian": 0.06,
        "Multiracial or other": 0.06,
    },
}

_LABELS = {
    "age": "Age",
    "gender": "Gender",
    "household_income": "Household income",
    "region": "US region",
    "race_ethnicity": "Race/ethnicity",
}


@dataclass(frozen=True)
class Persona:
    persona_id: str
    attributes: Mapping[str, str] = field(hash=False)

    def describe(self, labels: Mapping[str, str] | None = None) -> str:
        return "\n".join(f"- {attribute_label(k, labels)}: {v}"
                         for k, v in self.attributes.items() if v not in (None, ""))


def attribute_label(name: str, labels: Mapping[str, str] | None = None) -> str:
    if labels and name in labels:
        return labels[name]
    return _LABELS.get(name, name.replace("_", " ").capitalize())


class PersonaSampler:
    def __init__(self, marginals: Mapping[str, Mapping[str, float]] = US_ADULT_MARGINALS, seed: int = 0):
        self.marginals = {k: dict(v) for k, v in marginals.items()}
        for name, dist in self.marginals.items():
            total = sum(dist.values())
            if total <= 0:
                raise ValueError(f"Marginal for {name!r} has no mass")
            self.marginals[name] = {k: v / total for k, v in dist.items()}
        self.rng = np.random.default_rng(seed)

    def sample(self, n: int, prefix: str = "p") -> list[Persona]:
        draws = {name: self.rng.choice(list(dist), size=n, p=list(dist.values()))
                 for name, dist in self.marginals.items()}
        width = len(str(n))
        return [Persona(f"{prefix}{i:0{width}d}", {name: str(draws[name][i]) for name in self.marginals})
                for i in range(n)]


def load_personas(path: str | Path, id_column: str = "persona_id") -> list[Persona]:
    df = pd.read_csv(path, dtype=str).fillna("")
    if id_column not in df.columns:
        df[id_column] = [f"p{i}" for i in range(len(df))]
    attrs = [c for c in df.columns if c != id_column]
    return [Persona(row[id_column], {c: row[c] for c in attrs}) for _, row in df.iterrows()]
