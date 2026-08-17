"""
Knowledge Extractor — converts a raw concept string into a structured
educational knowledge model.
EU: Gemini 2.5 Flash on Vertex AI. US: Claude Haiku on Anthropic.
"""
import json
import logging
from services.ai_router import ai_complete

logger = logging.getLogger(__name__)

_SYSTEM = """You are an educational science expert and knowledge engineer.

Convert a learning concept into a structured knowledge model.

CRITICAL RULES:
- Do NOT describe images, visuals, or diagrams
- Extract pure scientific/educational knowledge only
- Be specific, accurate, and concise
- Every field must reflect real domain knowledge
- Return ONLY valid JSON — no explanation, no markdown

JSON schema (all fields required):
{
  "domain": "<physics|chemistry|mathematics|biology|geography|general>",
  "title": "<max 8 words describing the concept>",
  "learning_goal": "<one sentence: what the student understands after studying this>",
  "concept_type": "<force_diagram|energy_transfer|cycle|chemical_reaction|graph|anatomy|process_flow|comparison|hierarchy|circuit|wave|geometry|timeline>",
  "entities": ["<physical objects, substances, or agents involved>"],
  "relationships": [{"source": "<entity>", "target": "<entity>", "type": "<relationship type>"}],
  "variables": ["<measurable quantities relevant to this concept>"],
  "processes": ["<actions or changes occurring>"],
  "mechanisms": ["<underlying physical/chemical/biological principles>"],
  "must_show": ["<elements scientifically essential to convey the concept>"],
  "must_not_show": ["<visuals that are scientifically incorrect or misleading for this specific concept>"],
  "common_misconceptions": ["<what students typically get wrong>"],
  "difficulty": "<middle_school|high_school|undergraduate>"
}"""

_EXAMPLE_INPUT = "Hot coffee cools down because heat flows to the surroundings."
_EXAMPLE_OUTPUT = """{
  "domain": "physics",
  "title": "Heat Transfer from Coffee to Surroundings",
  "learning_goal": "Understand that heat flows spontaneously from a hotter object to a cooler environment until thermal equilibrium is reached",
  "concept_type": "energy_transfer",
  "entities": ["coffee", "surrounding air", "cup"],
  "relationships": [
    {"source": "coffee", "target": "surrounding air", "type": "heat_transfer"},
    {"source": "cup", "target": "surrounding air", "type": "conduction"}
  ],
  "variables": ["temperature", "internal energy", "heat flux", "time"],
  "processes": ["cooling", "thermal equilibration"],
  "mechanisms": ["conduction through cup walls", "convection in surrounding air", "radiation from surface", "evaporation from liquid surface"],
  "must_show": ["temperature difference indicated", "heat flow direction arrows", "system boundary between coffee and surroundings"],
  "must_not_show": ["heat particles", "temperature field lines", "energy stored as glowing balls", "work-energy conversion"],
  "common_misconceptions": ["heat is a substance stored in the coffee", "cold flows into the coffee from outside", "the coffee loses heat because it gets tired"],
  "difficulty": "high_school"
}"""


async def extract_knowledge_model(concept: str) -> dict:
    """
    Extract a structured knowledge model from a concept string.
    Falls back to a minimal model if AI call fails.
    """
    try:
        raw = await ai_complete(
            system=_SYSTEM,
            messages=[
                {"role": "user",      "content": _EXAMPLE_INPUT},
                {"role": "assistant", "content": _EXAMPLE_OUTPUT},
                {"role": "user",      "content": f"Extract knowledge model for:\n\n{concept}"},
            ],
            max_tokens=1200,
            temperature=0.3,
        )
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1][4:].strip() if parts[1].startswith("json") else parts[1].strip()
        model = json.loads(raw)
        logger.info("[know] domain=%s concept_type=%s", model.get("domain"), model.get("concept_type"))
        return model
    except Exception as e:
        logger.warning("[know] extraction failed (%s) — using fallback", e)
        return _fallback_model(concept)


def _fallback_model(concept: str) -> dict:
    return {
        "domain": "general",
        "title": concept[:60],
        "learning_goal": f"Understand {concept[:120]}",
        "concept_type": "process_flow",
        "entities": [],
        "relationships": [],
        "variables": [],
        "processes": [],
        "mechanisms": [],
        "must_show": [],
        "must_not_show": [],
        "common_misconceptions": [],
        "difficulty": "high_school",
    }
