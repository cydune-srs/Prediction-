"""Parse labelled final lines (e.g. 'PLAN: Classic', 'LIKELIHOOD: ...') out of an answer."""

from __future__ import annotations

import re

from synthpanel.prompts import ChoiceSpec, SurveySpec

UNPARSED = "unparsed"


def _line_pattern(label: str) -> re.Pattern:
    return re.compile(rf"^[ \t*_`>#-]*{re.escape(label)}[ \t]*:[ \t]*([^\n]*)$", re.IGNORECASE | re.MULTILINE)


def extract_line(text: str, label: str) -> tuple[str, str]:
    """Return (text with every `label:` line removed, value of the last such line or '')."""
    pattern = _line_pattern(label)
    matches = list(pattern.finditer(text))
    value = matches[-1].group(1).strip(" *_`\t\r") if matches else ""
    return pattern.sub("", text).strip(), value


def normalise_choice(raw: str, spec: ChoiceSpec) -> str:
    raw = raw.strip(" *_`.\t\r").lower()
    for option in spec.options:
        if raw and raw.startswith(option.lower()):
            return option
    return UNPARSED


def split_choice(text: str, spec: ChoiceSpec) -> tuple[str, str]:
    """Return (answer without the choice line, normalised choice). Last matching line wins."""
    clean, raw = extract_line(text, spec.label)
    return clean, normalise_choice(raw, spec)


def parse_answer(text: str, spec: SurveySpec) -> tuple[str, str, str]:
    """Return (answer without labelled lines, text to SSR-score, normalised choice).

    The text to score is the intent line when the spec has one and the respondent wrote it,
    otherwise the remaining answer.
    """
    clean, choice = text, ""
    intent_text = ""
    if spec.intent:
        clean, intent_text = extract_line(clean, spec.intent.label)
    if spec.choice:
        clean, choice = split_choice(clean, spec.choice)
    return clean, (intent_text or clean), choice
