"""Product concepts: what the synthetic respondent is shown."""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Concept:
    """A product or product concept to test.

    `concept_id` is the join key to ground truth (human survey rows, realized sales).
    `image_path` is optional: the paper showed respondents a concept slide, and Claude
    accepts images directly, so a slide or pack shot can be passed as-is.
    """

    concept_id: str
    name: str
    description: str = ""
    brand: str = ""
    category: str = ""
    price: str = ""
    image_path: str | None = None
    stimulus: str = ""  # if set, shown verbatim instead of the Product/Brand/... layout
    metadata: dict = field(default_factory=dict, hash=False, compare=False)

    def as_text(self) -> str:
        if self.stimulus:
            return self.stimulus.strip()
        lines = [f"Product: {self.name}"]
        if self.brand:
            lines.append(f"Brand: {self.brand}")
        if self.category:
            lines.append(f"Category: {self.category}")
        if self.price:
            lines.append(f"Price: {self.price}")
        lines.append(f"Description: {self.description.strip()}")
        return "\n".join(lines)

    def image_block(self) -> dict | None:
        if not self.image_path:
            return None
        path = Path(self.image_path)
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


_FIELDS = {"concept_id", "name", "description", "brand", "category", "price", "image_path", "stimulus"}


def load_concepts(path: str | Path) -> list[Concept]:
    """Load concepts from YAML (a list of mappings). Unknown keys go to `metadata`.

    Relative `image_path` values resolve against the YAML file's folder.
    """
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    concepts = []
    for item in raw:
        known = {k: v for k, v in item.items() if k in _FIELDS}
        extra = {k: v for k, v in item.items() if k not in _FIELDS}
        if known.get("image_path"):
            known["image_path"] = str((path.parent / known["image_path"]).resolve())
        known["concept_id"] = str(known["concept_id"])
        concepts.append(Concept(**known, metadata=extra))
    ids = [c.concept_id for c in concepts]
    if len(ids) != len(set(ids)):
        raise ValueError("concept_id values must be unique")
    return concepts
