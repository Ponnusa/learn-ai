"""
Diagram Planner — converts a knowledge model into a concrete diagram plan
using domain templates + Claude Haiku for layout decisions.
"""
import json
import logging
from services.ai_router import ai_complete
from .domain_templates import CONCEPT_TYPE_REQUIREMENTS, DOMAIN_STYLES

logger = logging.getLogger(__name__)

_SYSTEM = """You are an instructional design expert specialising in educational diagrams.

Given a structured knowledge model, design the most educationally effective diagram plan.

Rules:
- Every element must directly serve the stated learning goal
- Only include scientifically correct elements
- Prefer clarity and simplicity over completeness
- Do not invent elements not present in the knowledge model
- Return ONLY valid JSON — no explanation, no markdown

JSON schema:
{
  "diagram_type": "<same concept_type as the knowledge model>",
  "layout": "<brief description of spatial arrangement>",
  "panels": [{"title": "<panel name>", "elements": ["<specific drawable element>"]}],
  "labels": ["<every text label that must appear in the diagram>"],
  "color_scheme": "<description of color usage — keep it minimal>",
  "annotations": ["<arrows, callouts, dimension marks, or emphasis needed>"]
}"""


async def plan_diagram(knowledge_model: dict) -> dict:
    """
    Generate a diagram plan from a knowledge model.
    Uses the domain template as a hard constraint, Claude for layout.
    """
    concept_type = knowledge_model.get("concept_type", "process_flow")
    domain       = knowledge_model.get("domain", "general")
    template     = CONCEPT_TYPE_REQUIREMENTS.get(concept_type, {})

    user_msg = f"""Knowledge model:
{json.dumps(knowledge_model, indent=2)}

Domain style guide: {DOMAIN_STYLES.get(domain, DOMAIN_STYLES["general"])}

Template requirements for '{concept_type}':
- Required elements: {template.get("required_elements", [])}
- Style notes: {template.get("style_notes", "clean and clear")}
- Must avoid: {template.get("avoid", [])}

Design the diagram plan. Every element in 'panels' must be drawable.
Labels must include all entity names, variable values, and units."""

    try:
        raw = await ai_complete(
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=700,
            temperature=0.3,
        )
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1][4:].strip() if parts[1].startswith("json") else parts[1].strip()
        plan = json.loads(raw)
        logger.info("[plan] type=%s panels=%d labels=%d",
                    plan.get("diagram_type"), len(plan.get("panels", [])), len(plan.get("labels", [])))
        return plan
    except Exception as e:
        logger.warning("[plan] planner failed (%s) — using template fallback", e)
        return _template_fallback(knowledge_model, template, concept_type)


def _template_fallback(knowledge_model: dict, template: dict, concept_type: str) -> dict:
    """Build a minimal plan directly from the template when Claude fails."""
    entities  = knowledge_model.get("entities", [])
    must_show = knowledge_model.get("must_show", [])
    return {
        "diagram_type": concept_type,
        "layout": template.get("style_notes", "clear educational diagram"),
        "panels": [{
            "title": knowledge_model.get("title", "Diagram"),
            "elements": (template.get("required_elements", []) + must_show)[:10],
        }],
        "labels": entities + must_show,
        "color_scheme": "high contrast, white background, black outlines",
        "annotations": knowledge_model.get("relationships", []),
    }
