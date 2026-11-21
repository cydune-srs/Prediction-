"""Prompts for the synthetic respondent.

The respondent answers in free text; it is never asked for a number. Asking for a number
directly is what produces the narrow, skewed distributions SSR is designed to avoid.
"""

from __future__ import annotations

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


def user_content(concept: Concept, persona: Persona) -> list[dict]:
    """Concept first, persona second, so the concept prefix can be shared across respondents."""
    blocks: list[dict] = []
    image = concept.image_block()
    if image:
        blocks.append(image)
    blocks.append({"type": "text", "text": f"Here is the product concept you are being shown:\n\n{concept.as_text()}"})
    blocks.append({"type": "text", "text": f"You are this person:\n{persona.describe()}\n\n{QUESTION}"})
    return blocks
