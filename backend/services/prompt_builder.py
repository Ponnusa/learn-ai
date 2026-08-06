"""
Assembles the final system prompt for each student.

Structure:
  base_prompt  (AnimLearn verbatim — NEVER modified)
  + level_instruction  (deterministic from skill score)
  + ai_modifier  (AI-written, stored per student in DB)
  + misconception_reminders  (top 3 active)

For anonymous sessions: base prompt only (no profile yet).
"""
import json as _json
from database import get_db

# ─────────────────────────────────────────────────────────────────────────────
# BASE PROMPTS — copied verbatim from AnimLearn. Do NOT edit here.
# If you improve a prompt in AnimLearn, copy the updated version here.
# ─────────────────────────────────────────────────────────────────────────────

CHAT_SYSTEM_PROMPT = """You are an expert educational AI tutor. Your role is to explain
concepts clearly, accurately, and engagingly. You adapt your explanations to the student's
level and always ensure deep understanding rather than surface-level coverage.

When explaining concepts:
- Start with intuition before formalism
- Use concrete examples and analogies
- Connect new ideas to what the student already knows
- Highlight common misconceptions proactively
- For ALL mathematical and chemical notation use KaTeX/LaTeX syntax.
  ALWAYS use $...$ for inline math and $$...$$ for display/block equations.
  For display math, $$ MUST be on its own line: put $$ alone on one line, then the
  LaTeX content, then $$ alone on another line. NEVER write $$\begin{...} on one line.
  NEVER use \\[...\\] or \\(...\\) — those delimiters are not supported by the renderer.
  For simple chemical formulas prefer plain subscripts: $C_2H_4$, $H_2O$, $C_9H_8O_4$.
  Use $\\ce{}$ only for reaction arrows or charges, e.g. $\\ce{A -> B}$.
- When explaining a specific molecule or compound, include its SMILES string in a
  fenced code block tagged as `smiles` so a 2D structural diagram is rendered:
  ```smiles
  CC=C
  ```
  Include a SMILES block whenever showing the structure would help understanding
  (e.g. when first introducing a molecule, when discussing double bonds or ring
  systems). One molecule per block. Do NOT include SMILES for ions or reactions.
- Keep explanations focused — one key idea at a time

CONTINUITY RULES (critical):
- The conversation history shows what has already been explained. Treat it as shared
  knowledge — never re-explain a concept already covered unless the student explicitly
  asks or shows confusion about it.
- When building on a prior explanation, reference it briefly ("as we saw with the
  rocket example…") rather than repeating it.
- If the student asks something already answered, identify what specifically is still
  unclear and probe that gap instead of giving the full explanation again.

After explaining, suggest 2-3 follow-up directions the student might explore.
Format suggestions as a JSON array in your response metadata if asked.
"""

QUIZ_GENERATION_PROMPT = """You are an expert educational assessment designer.
Generate high-quality multiple-choice questions that test deep understanding,
not just memorization. Each question should:
- Test a specific concept or skill
- Have one clearly correct answer
- Have plausible distractors that reflect common misconceptions
- Include a detailed explanation for the correct answer

Return valid JSON array of question objects."""

VIDEO_TEACHING_PROMPT_TEMPLATE = """Create a clear educational animation that teaches
the following concept to students:\n\n{concept}"""

# ─────────────────────────────────────────────────────────────────────────────


def _score_to_instruction(score: int, subject: str) -> str:
    """Deterministic level instruction from score band."""
    if score < 25:
        return (
            f"The student is a true beginner in {subject} (score {score}/100). "
            "Use only simple everyday language — no jargon without immediate explanation. "
            "Lead with a relatable analogy before any theory. "
            "Break every concept into small digestible steps. "
            "Validate their understanding frequently. Never assume prior knowledge."
        )
    elif score < 45:
        return (
            f"The student is a lower-intermediate learner in {subject} (score {score}/100). "
            "Introduce technical terms slowly, always defining them. "
            "Use worked examples before formulas. "
            "Check understanding with a brief question at the end of explanations."
        )
    elif score < 65:
        return (
            f"The student has solid intermediate knowledge of {subject} (score {score}/100). "
            "Balance intuition with technical precision. "
            "You can use standard terminology but verify understanding of advanced terms. "
            "Offer both conceptual and mathematical views."
        )
    elif score < 82:
        return (
            f"The student is advanced in {subject} (score {score}/100). "
            "Use precise technical language. Skip basic definitions. "
            "Focus on deeper connections, edge cases, and 'why' — not just 'how'. "
            "Challenge them with higher-order questions."
        )
    else:
        return (
            f"The student is at expert level in {subject} (score {score}/100). "
            "Engage as a peer or near-peer. Discuss nuances, open problems, "
            "and research-level connections. Minimal scaffolding needed."
        )


def inject_conversation_context(
    prompt: str,
    summary: str | None,
    topics_covered: dict | None,
) -> str:
    """
    Appends rolling summary and topic map to an already-built system prompt.
    Called in chat.py after build_chat_prompt returns.
    """
    covered   = (topics_covered or {}).get("covered") or []
    weak      = (topics_covered or {}).get("weak_areas") or []
    has_context = bool(summary or covered or weak)

    if not has_context:
        return prompt

    block = "\n\n--- CONVERSATION CONTEXT ---"

    if summary:
        block += f"\n[What has been covered in this conversation]\n{summary}"

    if covered:
        block += f"\nTopics taught so far: {', '.join(covered)}."

    if weak:
        block += f"\nStudent showed confusion with: {', '.join(weak)} — watch for these."

    block += (
        "\nDo NOT re-explain any of the above unless the student's message shows "
        "they are still confused. Build on this foundation instead."
        "\n--- END CONTEXT ---"
    )

    return prompt + block


_LANGUAGE_NAMES = {"en": "English", "fi": "Finnish", "sv": "Swedish", "es": "Spanish", "fr": "French"}


async def build_chat_prompt(
    user_id: str | None,
    subject: str | None,
    language: str = "en",
    explanation_language: str | None = None,
    course_id: str | None = None,
) -> str:
    """
    Returns the full system prompt for a chat response.
    Always starts with the unchanged AnimLearn base.
    Personalisation is appended — never replaces the base.
    course_id is optional: non-nil only for TEKS-aligned courses.
    """
    prompt = CHAT_SYSTEM_PROMPT

    if explanation_language and explanation_language != language:
        # Bilingual mode: course in one language, explanations in another
        course_lang = _LANGUAGE_NAMES.get(language, language)
        explain_lang = _LANGUAGE_NAMES.get(explanation_language, explanation_language)
        prompt += (
            f"\n\nBILINGUAL MODE: The student's course materials are in {course_lang}, "
            f"but they want explanations in {explain_lang}. "
            f"Always respond in {explain_lang}. "
            f"When mentioning subject-specific terms, include the {course_lang} term in "
            f"parentheses so the student can match it to their textbook "
            f"(e.g. 'the integral (integraali) represents...'). "
            "Use direct UTF-8 characters, never HTML entities."
        )
    else:
        lang_name = _LANGUAGE_NAMES.get(language)
        if lang_name:
            prompt += (
                f"\n\nRespond entirely in {lang_name}. "
                "Use direct UTF-8 characters for all accented letters and special characters "
                "(write é not &eacute;, write ¿ not &#191;) — never use HTML entities."
            )

    # ── Curriculum context (TEKS-aligned courses only) ─────────────────────
    if course_id:
        from services.curriculum import get_curriculum_context, build_curriculum_block
        curriculum = await get_curriculum_context(course_id)
        if curriculum:
            prompt += build_curriculum_block(curriculum)

    if not user_id:
        return prompt  # anonymous: base + language + curriculum only

    async with get_db() as db:
        profile = await db.fetchrow(
            "SELECT * FROM student_profiles WHERE user_id = $1", user_id
        )

    if not profile:
        return prompt  # new registered user: base + language + curriculum only

    # ── Score-based level instruction ──────────────────────────────────────
    score = (profile["skill_scores"] or {}).get(subject or "General", 50)
    level_block = _score_to_instruction(score, subject or "this subject")

    # ── AI-written personal modifier ───────────────────────────────────────
    modifier = (profile["prompt_modifier"] or "").strip()

    # ── Misconception reminders (top 3) ────────────────────────────────────
    misconceptions = profile["known_misconceptions"] or []
    misc_block = ""
    if misconceptions:
        items = "; ".join(misconceptions[:3])
        misc_block = (
            f"\nKnown misconceptions to proactively address when relevant: {items}."
        )

    # ── Grade, goal, subject confidence ───────────────────────────────────────
    grade = profile["grade"] if profile["grade"] else None
    goal  = profile["goal"]  if profile["goal"]  else None
    sc    = profile["subject_confidence"] if profile["subject_confidence"] else {}
    if isinstance(sc, str):
        try:    sc = _json.loads(sc)
        except: sc = {}

    personalisation = "\n\n--- STUDENT PERSONALISATION ---\n"
    personalisation += level_block
    if grade:
        personalisation += f"\nGrade/level: {grade}."
    if goal:
        personalisation += f"\nLearning goal: {goal} — frame explanations toward this goal when relevant."
    if subject and sc.get(subject):
        personalisation += f"\nSelf-reported confidence in {subject}: {sc[subject]}."
    elif sc:
        top = ", ".join(f"{s}: {lv}" for s, lv in list(sc.items())[:4])
        personalisation += f"\nSubject confidence (self-reported): {top}."
    if modifier:
        personalisation += f"\n{modifier}"
    personalisation += misc_block

    return prompt + personalisation


STUDYSET_SYSTEM_PROMPT_TEMPLATE = (
    'You are a focused study tutor for the set "{title}" ({subject}).\n\n'
    "Answer the student's questions ONLY based on the material provided below. "
    "If the answer is not in the material, say so clearly — do not guess. "
    "Be concise, clear, and educational. Cite specific points when helpful.\n"
    "For mathematical or chemical notation use KaTeX/LaTeX: $...$ inline, $$...$$ for blocks.\n\n"
    "CONTINUITY RULES (critical):\n"
    "- Do not re-explain concepts already covered in this conversation.\n"
    "- Reference prior explanations briefly and build on them.\n"
    "- If the student asks something already answered, probe what's still unclear.\n\n"
    "--- STUDY MATERIAL ---\n"
    "{material}\n"
    "--- END OF MATERIAL ---"
)


async def build_studyset_prompt(
    title: str,
    subject: str | None,
    material_text: str,
    user_id: str | None,
    language: str = "en",
    focus_concept: dict | None = None,
) -> str:
    """
    Returns the full system prompt for a grounded studyset chat response.
    Applies student personalisation from the profile if user_id is provided.
    When focus_concept is set, the AI prioritises that concept in its responses.
    """
    prompt = STUDYSET_SYSTEM_PROMPT_TEMPLATE.format(
        title=title,
        subject=subject or "General",
        material=material_text[:60_000],
    )

    if focus_concept:
        prompt += (
            "\n\n--- CURRENT FOCUS ---\n"
            f"The student is currently focusing on: \"{focus_concept['name']}\"\n"
            f"Definition: {focus_concept['definition']}\n"
            f"Explanation: {focus_concept['explanation']}\n"
            "Prioritise this concept in your responses. When the student's question "
            "relates to this topic, ground your answer primarily in the above definition "
            "and explanation, using the full study material for additional context.\n"
            "--- END FOCUS ---"
        )

    lang_name = _LANGUAGE_NAMES.get(language)
    if lang_name:
        prompt += (
            f"\n\nRespond entirely in {lang_name}. "
            "Use direct UTF-8 characters for all accented letters and special characters "
            "(write é not &eacute;, write ¿ not &#191;) — never use HTML entities."
        )

    if not user_id:
        return prompt

    async with get_db() as db:
        profile = await db.fetchrow(
            "SELECT * FROM student_profiles WHERE user_id = $1", user_id
        )
    if not profile:
        return prompt

    score       = (profile["skill_scores"] or {}).get(subject or "General", 50)
    level_block = _score_to_instruction(score, subject or "this subject")
    modifier    = (profile["prompt_modifier"] or "").strip()
    misconceptions = profile["known_misconceptions"] or []
    misc_block  = ""
    if misconceptions:
        items      = "; ".join(misconceptions[:3])
        misc_block = f"\nKnown misconceptions to address when relevant: {items}."

    # ── Grade, goal, subject confidence ───────────────────────────────────────
    grade = profile["grade"] if profile["grade"] else None
    goal  = profile["goal"]  if profile["goal"]  else None
    sc    = profile["subject_confidence"] if profile["subject_confidence"] else {}
    if isinstance(sc, str):
        try:    sc = _json.loads(sc)
        except: sc = {}

    personalisation  = "\n\n--- STUDENT PERSONALISATION ---\n"
    personalisation += level_block
    if grade:
        personalisation += f"\nGrade/level: {grade}."
    if goal:
        personalisation += f"\nLearning goal: {goal} — frame explanations toward this goal when relevant."
    if subject and sc.get(subject):
        personalisation += f"\nSelf-reported confidence in {subject}: {sc[subject]}."
    elif sc:
        top = ", ".join(f"{s}: {lv}" for s, lv in list(sc.items())[:4])
        personalisation += f"\nSubject confidence (self-reported): {top}."
    if modifier:
        personalisation += f"\n{modifier}"
    personalisation += misc_block

    return prompt + personalisation


_GRADE_DEPTH: dict[str, str] = {
    "Grade 6–8":      "introductory — everyday analogies, no algebra, simple visuals and clear labels",
    "Grade 9–10":     "intermediate — algebra and geometry OK, connect to classroom context",
    "Grade 11–12":    "upper-secondary — pre-calculus OK, connect to exam topics and deeper mechanism",
    "Undergrad Y1–2": "undergraduate introductory — assume standard prerequisites, derive from first principles",
    "Undergrad Y3–4": "advanced undergraduate — go deep on mechanism and derivation, peer-level language",
    "Graduate":       "graduate — research-level connections, nuance, open questions",
    "Self-learner":   "intermediate — clear intuition first, examples before formulas, no assumed curriculum",
}


async def build_video_prompt(
    concept_text: str,
    user_id: str | None,
    subject: str | None,
    language: str = "en",
    grade_level: str | None = None,
) -> str:
    """
    Frames the concept for the Manim pipeline.
    Depth hint comes from (in priority order):
      1. Student skill score (logged-in users with profile)
      2. grade_level passed from frontend (all users including anonymous)
      3. Default intermediate fallback
    """
    depth = "intermediate — balance visual intuition with key equations"

    if user_id:
        async with get_db() as db:
            profile = await db.fetchrow(
                "SELECT skill_scores, grade FROM student_profiles WHERE user_id = $1", user_id
            )
        if profile:
            score = (profile["skill_scores"] or {}).get(subject or "General", 50)
            if score < 35:
                depth = "introductory — use simple visuals, minimal notation, clear labels"
            elif score >= 65:
                depth = "advanced — include full derivation steps and precise notation"
            # Fill grade_level from profile if not supplied by frontend
            if not grade_level and profile["grade"]:
                grade_level = profile["grade"]

    # Grade-level depth overrides the default but not the skill-score-derived depth
    # (skill score is more precise; grade is a fallback for anonymous/new users)
    if grade_level and depth == "intermediate — balance visual intuition with key equations":
        depth = _GRADE_DEPTH.get(grade_level, depth)

    prompt = VIDEO_TEACHING_PROMPT_TEMPLATE.format(concept=concept_text[:2000])
    prompt += f"\n\nTarget depth: {depth}."
    if grade_level:
        prompt += f"\nStudent level: {grade_level}."
    lang_name = _LANGUAGE_NAMES.get(language)
    if lang_name:
        prompt += f"\n\nWrite ALL narration text and labels in {lang_name}."
    return prompt
