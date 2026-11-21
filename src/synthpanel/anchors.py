"""Likert anchor statements.

Each anchor set holds one reference statement per Likert point (1 = definitely would not
buy ... 5 = definitely would buy). SSR scores a free-text answer against every set and
averages the resulting distributions, which reduces sensitivity to any one wording.

The paper used six anchor sets. Its exact wording is not reproduced here; these sets are
our own and should be tuned on a human-labelled survey before production use
(see `synthpanel.validation.human`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AnchorSet:
    """One reference statement per Likert point, ordered from lowest to highest."""

    statements: tuple[str, ...]
    name: str = ""

    def __post_init__(self) -> None:
        if len(self.statements) < 2:
            raise ValueError("An anchor set needs at least two statements.")

    @property
    def n_points(self) -> int:
        return len(self.statements)


DEFAULT_PURCHASE_INTENT_ANCHORS: tuple[AnchorSet, ...] = (
    AnchorSet(
        name="direct",
        statements=(
            "I definitely would not buy this.",
            "I probably would not buy this.",
            "I might or might not buy this.",
            "I probably would buy this.",
            "I definitely would buy this.",
        ),
    ),
    AnchorSet(
        name="likelihood",
        statements=(
            "There is no chance I would purchase this product.",
            "It is unlikely that I would purchase this product.",
            "I am unsure whether I would purchase this product.",
            "It is likely that I would purchase this product.",
            "I am certain I would purchase this product.",
        ),
    ),
    AnchorSet(
        name="interest",
        statements=(
            "This product does not interest me at all and I would never spend money on it.",
            "This product doesn't really appeal to me, so I would most likely skip it.",
            "This product is okay; I could go either way on buying it.",
            "This product appeals to me and I would probably pick it up.",
            "I love this product and would buy it as soon as I could.",
        ),
    ),
    AnchorSet(
        name="shopping",
        statements=(
            "If I saw this in the store I would walk right past it.",
            "If I saw this in the store I would probably leave it on the shelf.",
            "If I saw this in the store I might consider it, depending on the day.",
            "If I saw this in the store I would probably put it in my cart.",
            "If I saw this in the store I would put it in my cart without hesitation.",
        ),
    ),
    AnchorSet(
        name="switching",
        statements=(
            "I would stick with what I already use; this is not for me.",
            "I doubt I would switch to this from what I use now.",
            "I might try this, but I am not sure it would replace what I use.",
            "I would probably try this instead of what I usually buy.",
            "I would definitely switch to this product.",
        ),
    ),
    AnchorSet(
        name="value",
        statements=(
            "This is not worth my money at all.",
            "This is probably not worth the price for me.",
            "It might be worth it; I am undecided.",
            "This seems worth the price and I would likely buy it.",
            "This is great value and I would definitely buy it.",
        ),
    ),
)


def load_anchor_sets(path: str | Path) -> tuple[AnchorSet, ...]:
    """Load anchor sets from YAML: a list of {name, statements: [...]} mappings."""
    raw = yaml.safe_load(Path(path).read_text())
    sets = tuple(AnchorSet(name=item.get("name", f"set{i}"), statements=tuple(item["statements"]))
                 for i, item in enumerate(raw))
    sizes = {s.n_points for s in sets}
    if len(sizes) != 1:
        raise ValueError(f"All anchor sets must have the same number of points, got {sorted(sizes)}.")
    return sets
