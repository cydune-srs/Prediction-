"""synthpanel: synthetic consumer panels scored with Semantic Similarity Rating (SSR).

Method: Maier et al., "LLMs Reproduce Human Purchase Intent via Semantic Similarity
Elicitation of Likert Ratings" (PyMC Labs / Colgate-Palmolive). An LLM answers a
purchase-intent question in free text as a given persona; the answer is embedded and
compared with anchor statements for each Likert point, producing a probability
distribution over the 1-5 scale instead of a single forced number.
"""

from synthpanel.anchors import AnchorSet, DEFAULT_PURCHASE_INTENT_ANCHORS
from synthpanel.concepts import Concept, load_concepts
from synthpanel.personas import Persona, PersonaSampler, load_personas
from synthpanel.ssr import SSRScorer
from synthpanel.survey import SurveyResult, run_survey

__all__ = [
    "AnchorSet",
    "DEFAULT_PURCHASE_INTENT_ANCHORS",
    "Concept",
    "load_concepts",
    "Persona",
    "PersonaSampler",
    "load_personas",
    "SSRScorer",
    "SurveyResult",
    "run_survey",
]
