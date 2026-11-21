"""Study definitions: one YAML file describes panels, the offers each panel sees, and scoring.

A study has one or more panels. Each panel has its own respondents (persona marginals),
question, optional stated-choice line, Likert anchors, and cells (the offers/scenarios
shown). Every persona in a panel answers every cell in an independent call, so cells can be
compared within-persona against the panel's control cell.

Cells can carry `revenue`: monthly revenue for each stated choice (e.g. Black Card 27.99,
Classic 15, Not joining 0), which `pricing.py` turns into revenue per respondent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from synthpanel.anchors import AnchorSet
from synthpanel.concepts import Concept
from synthpanel.personas import Persona, PersonaSampler
from synthpanel.prompts import SYSTEM_PROMPT, ChoiceSpec, IntentSpec, SurveySpec


@dataclass
class Panel:
    name: str
    n: int
    seed: int
    spec: SurveySpec
    anchors: tuple[AnchorSet, ...]
    marginals: dict[str, dict[str, float]]
    cells: list[Concept]
    control: str
    scale_label: str = ""

    def personas(self) -> list[Persona]:
        return PersonaSampler(self.marginals, seed=self.seed).sample(self.n, prefix=f"{self.name}-")

    def cell(self, cell_id: str) -> Concept:
        for c in self.cells:
            if c.concept_id == cell_id:
                return c
        raise KeyError(cell_id)

    def revenue(self, cell_id: str) -> dict[str, float]:
        return {str(k): float(v) for k, v in self.cell(cell_id).metadata.get("revenue", {}).items()}


@dataclass
class Study:
    name: str
    model: str
    embedder: str
    temperature: float
    max_tokens: int
    panels: dict[str, Panel]
    notes: str = ""
    sources: list = field(default_factory=list)


def _anchors(raw: list[dict]) -> tuple[AnchorSet, ...]:
    sets = tuple(AnchorSet(name=a.get("name", f"set{i}"), statements=tuple(a["statements"])) for i, a in enumerate(raw))
    if len({s.n_points for s in sets}) != 1:
        raise ValueError("All anchor sets in a panel must have the same number of points.")
    return sets


def load_study(path: str | Path) -> Study:
    raw = yaml.safe_load(Path(path).read_text())
    system_prompt = raw.get("system_prompt", SYSTEM_PROMPT)
    labels = raw.get("labels", {})
    panels = {}
    for name, p in raw["panels"].items():
        choice = ChoiceSpec(p["choice"]["label"], tuple(p["choice"]["options"])) if p.get("choice") else None
        intent = IntentSpec(p["intent"]["label"], p["intent"]["prompt"]) if p.get("intent") else None
        spec = SurveySpec(system_prompt=p.get("system_prompt", system_prompt), question=p["question"],
                          concept_intro=p.get("concept_intro", ""), choice=choice, intent=intent, labels=labels)
        cells = []
        for c in p["cells"]:
            extra = {k: v for k, v in c.items() if k not in {"id", "name", "stimulus"}}
            cells.append(Concept(concept_id=str(c["id"]), name=c.get("name", c["id"]),
                                 stimulus=c["stimulus"], metadata=extra))
        if choice:
            for c in cells:
                missing = set(choice.options) - set(map(str, c.metadata.get("revenue", {})))
                if c.metadata.get("revenue") and missing:
                    raise ValueError(f"Cell {c.concept_id}: revenue is missing choice options {sorted(missing)}")
        control = str(p.get("control", cells[0].concept_id))
        if control not in {c.concept_id for c in cells}:
            raise ValueError(f"Panel {name}: control {control!r} is not one of its cells")
        panels[name] = Panel(name=name, n=int(p["n"]), seed=int(p.get("seed", 0)), spec=spec,
                             anchors=_anchors(p["anchors"]), marginals=p["marginals"], cells=cells,
                             control=control, scale_label=p.get("scale_label", ""))
    return Study(name=raw["name"], model=raw.get("model", "claude-opus-5-5"),
                 embedder=raw.get("embedder", "voyage"), temperature=float(raw.get("temperature", 1.0)),
                 max_tokens=int(raw.get("max_tokens", 400)), panels=panels,
                 notes=raw.get("notes", ""), sources=raw.get("sources", []))
