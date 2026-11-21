"""Prompts for the synthetic respondent.

The respondent answers in free text; it is never asked for a Likert number. Asking for a
number directly is what produces the narrow, skewed distributions SSR is designed to avoid.
A study may also ask for a discrete choice (e.g. which plan) on a final labelled line; that
line is parsed out and removed before SSR scoring.

The text layout here is the single source of truth: the Snowflake Cortex backend renders
the same template in SQL (see `backends/cortex.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from synthpanel.concepts import Concept
from synthpanel.personas import Persona

SYSTEM_PROMPT = """You are taking part in a consumer research survey as the person described in the \
user's message. Answer as that person would in real life: draw on their likely budget, habits, \
household needs and tastes. Real shoppers are often indifferent or unconvinced, and many concepts \
do not appeal to most people, so do not default to enthusiasm.

Reply in two to four sentences of plain first-person speech. Say how likely you would be to buy \
the product and why. Do not give a numeric rating, a score or a scale point, and do not mention \
that you are an AI or that this is a simulation."""

QUESTION = "How likely would you be to purchase this product?"

CONCEPT_INTRO = "Here is the product concept you are being shown:\n\n"
PERSONA_INTRO = "You are this person:\n"


@dataclass(frozen=True)
class ChoiceSpec:
    """A discrete choice the respondent states on a final line, e.g. 'PLAN: Classic'."""

    label: str
    options: tuple[str, ...]

    def line(self) -> str:
        return f"{self.label}: <one of: {' | '.join(self.options)}>"


@dataclass(frozen=True)
class IntentSpec:
    """A one-sentence, free-text intent statement on its own line; SSR scores only this line.

    Use it when the question is compound (e.g. 'would you join, and which plan?'): the full
    answer is dominated by plan details, which dilutes the embedding signal for intent.
    """

    label: str
    prompt: str

    def line(self) -> str:
        return f"{self.label}: <{self.prompt}>"


@dataclass(frozen=True)
class SurveySpec:
    system_prompt: str = SYSTEM_PROMPT
    question: str = QUESTION
    concept_intro: str = CONCEPT_INTRO
    choice: ChoiceSpec | None = None
    intent: IntentSpec | None = None
    labels: dict = field(default_factory=dict, hash=False, compare=False)

    def concept_text(self, concept: Concept) -> str:
        return f"{self.concept_intro}{concept.as_text()}"

    def tail(self) -> str:
        lines = [s.line() for s in (self.intent, self.choice) if s]
        if not lines:
            return ""
        head = "add one final line" if len(lines) == 1 else "add these final lines"
        return f"\n\nAfter your answer, {head} in exactly this form:\n" + "\n".join(lines)

    def persona_text(self, persona: Persona) -> str:
        return f"{PERSONA_INTRO}{persona.describe(self.labels)}\n\n{self.question}{self.tail()}"


DEFAULT_SPEC = SurveySpec()


def user_content(concept: Concept, persona: Persona, spec: SurveySpec = DEFAULT_SPEC) -> list[dict]:
    """Concept first, persona second, so the concept prefix can be shared across respondents."""
    blocks: list[dict] = []
    image = concept.image_block()
    if image:
        blocks.append(image)
    blocks.append({"type": "text", "text": spec.concept_text(concept)})
    blocks.append({"type": "text", "text": spec.persona_text(persona)})
    return blocks


def user_text(concept: Concept, persona: Persona, spec: SurveySpec = DEFAULT_SPEC) -> str:
    """The same content as one string (used by text-only backends such as Cortex)."""
    return f"{spec.concept_text(concept)}\n\n{spec.persona_text(persona)}"
