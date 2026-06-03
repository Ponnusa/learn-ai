"""
Diagram Validator — catches scientific errors and bad visuals
in a diagram plan BEFORE it reaches the image generator.
"""
import logging
from .domain_templates import BAD_VISUALS, CONCEPT_TYPE_REQUIREMENTS

logger = logging.getLogger(__name__)


def validate_diagram_plan(plan: dict, knowledge_model: dict) -> list[str]:
    """
    Check the diagram plan against:
      1. Global BAD_VISUALS red-flag list
      2. must_not_show from the knowledge model
      3. Concept-type template avoid list

    Returns a list of issue strings (empty = clean).
    Issues are non-blocking — they're passed as correction hints
    to the prompt builder, not hard failures.
    """
    issues: list[str] = []
    plan_text = str(plan).lower()

    # 1. Global bad-visual scan
    for bad in BAD_VISUALS:
        if bad.lower() in plan_text:
            issues.append(f"Forbidden visual: '{bad}'")

    # 2. Knowledge-model must_not_show
    for forbidden in knowledge_model.get("must_not_show", []):
        if forbidden.lower() in plan_text:
            issues.append(f"Scientifically misleading for this concept: '{forbidden}'")

    # 3. Concept-type template avoid list
    concept_type = plan.get("diagram_type") or knowledge_model.get("concept_type", "")
    for avoid_item in CONCEPT_TYPE_REQUIREMENTS.get(concept_type, {}).get("avoid", []):
        if avoid_item.lower() in plan_text:
            issues.append(f"Template violation ({concept_type}): avoid '{avoid_item}'")

    if issues:
        logger.warning("[valid] %d issue(s) detected pre-generation: %s", len(issues), issues)
    else:
        logger.info("[valid] plan clean — no issues detected")

    return issues
