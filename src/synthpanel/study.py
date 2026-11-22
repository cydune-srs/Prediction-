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
    # Stratified (balanced) attributes: every combination of levels gets an equal share of
    # personas, in a fixed rotation by persona index. Use for the factors you want to read
    # results by; weight back to a population with `strata_weights`.
    strata: dict[str, list[str]] = field(default_factory=dict)
    strata_weights: dict[str, dict[str, float]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    # Pre-built personas (CSV with persona_id + attribute columns), e.g. from real store
    # trade areas. Columns starting with '_' (weights, IDs) are kept but not shown to respondents.
    persona_file: str | None = None

    def _file_personas(self) -> list[Persona]:
        from synthpanel.personas import load_personas
        return load_personas(self.persona_file)

    @property
    def attribute_order(self) -> list[str]:
        if self.persona_file:
            return list(self._file_personas()[0].attributes)
        names = list(self.marginals) + [s for s in self.strata if s not in self.marginals]
        if self.order:
            missing = set(names) - set(self.order)
            if missing:
                raise ValueError(f"Panel {self.name}: `order` is missing {sorted(missing)}")
            return list(self.order)
        return names

    def stratum_levels(self, idx: int) -> dict[str, str]:
        """Balanced assignment: persona idx -> one level per stratified attribute."""
        out, block = {}, 1
        for name, levels in self.strata.items():
            out[name] = levels[(idx // block) % len(levels)]
            block *= len(levels)
        return out

    def personas(self) -> list[Persona]:
        if self.persona_file:
            return self._file_personas()
        sampled = PersonaSampler(self.marginals, seed=self.seed).sample(self.n, prefix=f"{self.name}-")
        if not self.strata:
            return sampled
        out = []
        for i, p in enumerate(sampled):
            attrs = {**p.attributes, **self.stratum_levels(i)}
            out.append(Persona(p.persona_id, {k: attrs[k] for k in self.attribute_order}))
        return out

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
        template = p.get("stimulus_template")
        for c in p["cells"]:
            extra = {k: v for k, v in c.items() if k not in {"id", "name", "stimulus"}}
            stimulus = c.get("stimulus") or (template.format(**c.get("vars", {})) if template else None)
            if not stimulus:
                raise ValueError(f"Cell {c['id']}: needs `stimulus`, or `vars` with a panel `stimulus_template`")
            cells.append(Concept(concept_id=str(c["id"]), name=c.get("name", c["id"]),
                                 stimulus=stimulus, metadata=extra))
        if choice:
            for c in cells:
                missing = set(choice.options) - set(map(str, c.metadata.get("revenue", {})))
                if c.metadata.get("revenue") and missing:
                    raise ValueError(f"Cell {c.concept_id}: revenue is missing choice options {sorted(missing)}")
        control = str(p.get("control", cells[0].concept_id))
        if control not in {c.concept_id for c in cells}:
            raise ValueError(f"Panel {name}: control {control!r} is not one of its cells")
        strata = {k: [str(v) for v in levels] for k, levels in (p.get("strata") or {}).items()}
        weights = p.get("strata_weights") or {}
        for attr, w in weights.items():
            if attr not in strata or set(map(str, w)) != set(strata[attr]):
                raise ValueError(f"Panel {name}: strata_weights[{attr!r}] must cover exactly the levels of strata[{attr!r}]")
        panel = Panel(name=name, n=int(p.get("n", 0)), seed=int(p.get("seed", 0)), spec=spec,
                      anchors=_anchors(p["anchors"]), marginals=p.get("marginals") or {}, cells=cells,
                      control=control, scale_label=p.get("scale_label", ""), strata=strata,
                      strata_weights={a: {str(k): float(v) for k, v in w.items()} for a, w in weights.items()},
                      order=list(p.get("order") or []),
                      persona_file=str((Path(path).parent / p["persona_file"]).resolve()) if p.get("persona_file") else None)
        if panel.persona_file:
            panel.n = len(panel.personas())
        panel.attribute_order  # validates `order`
        panels[name] = panel
    return Study(name=raw["name"], model=raw.get("model", "claude-opus-5-5"),
                 embedder=raw.get("embedder", "voyage"), temperature=float(raw.get("temperature", 1.0)),
                 max_tokens=int(raw.get("max_tokens", 400)), panels=panels,
                 notes=raw.get("notes", ""), sources=raw.get("sources", []))
