"""
Curriculum context service — TEKS-aligned prompt injection.

Completely isolated from the existing course builder. Courses without a
curriculum_context_id return None from get_curriculum_context(), which
means zero change to existing prompts for all non-pilot courses.
"""
from __future__ import annotations
from database import get_db


async def get_curriculum_context(course_id: str) -> dict | None:
    """
    Returns the curriculum context for a course, or None if not configured.
    Called by build_chat_prompt — safe to call for any course_id.
    """
    try:
        async with get_db() as db:
            row = await db.fetchrow(
                """
                SELECT cc.*
                FROM curriculum_contexts cc
                JOIN courses c ON c.curriculum_context_id = cc.id
                WHERE c.id = $1::uuid
                """,
                course_id,
            )
        return dict(row) if row else None
    except Exception:
        return None  # never break chat if curriculum lookup fails


def build_curriculum_block(ctx: dict) -> str:
    """
    Formats a curriculum_context row into a system prompt block.
    Only called when get_curriculum_context returns a non-None value.
    """
    lines = ["\n\n--- CURRICULUM CONTEXT ---"]

    if ctx.get("driving_question"):
        lines.append(f"Unit Driving Question: {ctx['driving_question']}")

    if ctx.get("grade_level") and ctx.get("subject"):
        lines.append(f"Class: {ctx['grade_level']} {ctx['subject']}")

    if ctx.get("teks_codes"):
        codes = ", ".join(ctx["teks_codes"])
        lines.append(f"TEKS Standards: {codes}")

    active = ctx.get("active_lesson", 1)
    total  = ctx.get("lesson_count", 1)
    lines.append(f"Current Lesson: {active} of {total}")

    key_ideas = ctx.get("key_ideas") or []
    if isinstance(key_ideas, str):
        import json
        try:
            key_ideas = json.loads(key_ideas)
        except Exception:
            key_ideas = []
    if key_ideas:
        lines.append(
            "\nKey ideas students should FIGURE OUT through inquiry "
            "(guide them toward these — never state them directly):"
        )
        for idea in key_ideas:
            lines.append(f"  • {idea}")

    vocabulary = ctx.get("vocabulary") or []
    if vocabulary:
        lines.append(f"\nUnit vocabulary: {', '.join(vocabulary)}")

    if ctx.get("inquiry_guardrail"):
        lines.append(f"\nPedagogy: {ctx['inquiry_guardrail']}")

    lines.append("--- END CURRICULUM CONTEXT ---")
    return "\n".join(lines)
