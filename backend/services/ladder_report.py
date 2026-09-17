"""
Ladder session report generation.

Turns a resolved guided-discovery (Socratic ladder) chain into a structured,
rubric-scored outcome report a teacher can read: overall understanding
level, four "thinking radar" dimensions each with their own level/evidence/
confidence/next-step, strengths, areas for growth, next steps, one teacher
coaching note, and a suggested next topic. Same shape as the report format
this feature was designed against.

Runs as a FastAPI BackgroundTask, fired right after the resolving chat
response has already been sent to the student — this is a second, heavier
AI call, and nobody should wait on it to see their own reply. Failure here
never surfaces to the student; it just leaves the row in 'failed' status.
"""
import json
import logging

from database import get_db
from services.ai_router import openai_client

logger = logging.getLogger(__name__)

REPORT_DIMENSIONS = ("decision_making", "justification", "constraint_awareness", "transfer")

# Local copy of the small language-code map used throughout routers/courses.py
# — duplicated rather than imported to avoid a services -> routers dependency.
_LANGUAGE_NAMES = {'fi': 'Finnish', 'sv': 'Swedish', 'es': 'Spanish', 'fr': 'French', 'no': 'Norwegian'}

_REPORT_SYSTEM_PROMPT = """You are an expert learning-assessment analyst.

You will be given a transcript of a guided-discovery (Socratic) tutoring
exchange between an AI tutor and a student on one specific concept, ending
in the student reaching a resolved understanding. Produce a structured
evaluation of the STUDENT's reasoning shown in this transcript ONLY — never
invent claims they didn't make, and never evaluate the tutor.

Score generously but honestly: if a dimension was never actually exercised
in this transcript, say so plainly ("Limited Evidence" as the level, and
explain in observable_evidence that it wasn't activated) rather than
guessing or inflating it.

Return ONLY a JSON object with exactly this shape (no markdown fences, no
extra keys):
{
  "academic_understanding": {
    "level": "Beginner|Developing|Proficient|Advanced",
    "summary": "2-3 sentences on what the student showed, referencing specifics from the transcript"
  },
  "thinking_radar": {
    "decision_making":      { "level": "...", "description": "...", "confidence": "High|Medium|Low|Insufficient", "observable_evidence": ["..."], "support_level": "Independent|Occasional prompting|Heavy prompting|Not applicable", "next_growth_step": "..." },
    "justification":        { "level": "...", "description": "...", "confidence": "...", "observable_evidence": ["..."], "support_level": "...", "next_growth_step": "..." },
    "constraint_awareness": { "level": "...", "description": "...", "confidence": "...", "observable_evidence": ["..."], "support_level": "...", "next_growth_step": "..." },
    "transfer":              { "level": "...", "description": "...", "confidence": "...", "observable_evidence": ["..."], "support_level": "...", "next_growth_step": "..." }
  },
  "strengths": ["...", "..."],
  "areas_for_growth": ["...", "..."],
  "next_steps": ["...", "..."],
  "teacher_insight": "one specific, actionable coaching note for the teacher — the single most useful thing to know",
  "suggested_next_topic": "a concrete next topic building on this one",
  "optional_extension": "an optional stretch/enrichment idea for a student who's ready to go further"
}

Dimension meanings:
- decision_making: did the student weigh alternatives and commit to a reasoned position, rather than just repeating a fact?
- justification: did the student explain WHY — connecting cause to effect, or evidence to claim — not just WHAT?
- constraint_awareness: did the student identify limiting factors, assumptions, or conditions relevant to the question?
- transfer: did the student apply the idea to a new example or context beyond the one directly discussed? Mark "Limited Evidence" if the transcript never actually gave them that opportunity — don't penalize for a chance that never came up, say plainly it wasn't activated this session.

Level bands, weakest to strongest: Limited Evidence, Beginner, Developing,
Proficient, Advanced. Use "Limited Evidence" whenever the transcript
doesn't show enough to judge a dimension, for either academic_understanding
or any individual thinking_radar dimension."""


def _build_user_prompt(transcript_text: str, concept_title: str, subject: str | None, grade_level: str | None) -> str:
    return (
        f"CONCEPT: {concept_title}\n"
        f"SUBJECT: {subject or 'General'}\n"
        f"GRADE LEVEL: {grade_level or 'Unknown'}\n\n"
        f"TRANSCRIPT (tutor and student alternating, oldest first):\n{transcript_text}"
    )


async def generate_ladder_report(report_id: str) -> None:
    """
    Background task: load the report row + the resolved chain's transcript,
    call the model, store the structured result. Never raises — this runs
    detached from any request, so a failure just marks the row 'failed'
    with an error_message for later inspection rather than surfacing
    anywhere live.
    """
    try:
        async with get_db() as db:
            row = await db.fetchrow("""
                SELECT lsr.id, lsr.conversation_id, lsr.topic,
                       gde.message_id, gde.steps,
                       m.metadata AS resolving_metadata,
                       cc.title   AS concept_title,
                       co.subject AS concept_subject,
                       co.grade   AS course_grade,
                       tu.language AS teacher_language
                FROM ladder_session_reports lsr
                JOIN guided_discovery_events gde ON gde.id = lsr.guided_discovery_event_id
                JOIN messages m ON m.id = gde.message_id
                LEFT JOIN course_concepts cc ON cc.id = lsr.concept_id
                LEFT JOIN course_units cu    ON cu.id = cc.unit_id
                LEFT JOIN courses co          ON co.id = cu.course_id
                LEFT JOIN users tu             ON tu.id = co.teacher_id
                WHERE lsr.id = $1::uuid
            """, report_id)
        if not row:
            logger.warning(f"[ladder_report] report {report_id} not found — skipping")
            return

        # Pull enough trailing history to comfortably cover the whole chain
        # (steps scaffolding turns + their student replies + the resolving
        # turn), rather than trying to pin down exact chain boundaries —
        # the concept/subject context given below keeps the model focused
        # on what's actually relevant.
        limit = (row["steps"] + 1) * 2 + 2
        async with get_db() as db:
            msgs = await db.fetch("""
                SELECT role, content FROM messages
                WHERE conversation_id = $1::uuid
                  AND created_at <= (SELECT created_at FROM messages WHERE id = $2::uuid)
                ORDER BY created_at DESC LIMIT $3
            """, row["conversation_id"], row["message_id"], limit)
        msgs = list(reversed(msgs))

        if not msgs:
            raise RuntimeError("no transcript messages found for this chain")

        transcript_text = "\n\n".join(
            f"{'STUDENT' if m['role'] == 'user' else 'TUTOR'}: {m['content']}" for m in msgs
        )

        # The transfer-check exchange (see courses.py's _generate_transfer_check)
        # only ever lives in the resolving message's metadata, never in a
        # message's own content — so without this, the transcript above cuts
        # off before it and the model scoring "Transfer" never sees the one
        # piece of evidence that actually proves it happened, even though a
        # report only exists here because that check was answered correctly.
        resolving_meta = row["resolving_metadata"]
        if isinstance(resolving_meta, str):
            try:    resolving_meta = json.loads(resolving_meta)
            except: resolving_meta = {}
        tc = (resolving_meta or {}).get("transfer_check")
        if tc and tc.get("status") in ("correct", "wrong"):
            options      = tc.get("options") or []
            chosen_idx   = tc.get("chosen_idx")
            correct_idx  = tc.get("correct_idx")
            chosen_text  = options[chosen_idx] if isinstance(chosen_idx, int) and 0 <= chosen_idx < len(options) else "?"
            correct_text = options[correct_idx] if isinstance(correct_idx, int) and 0 <= correct_idx < len(options) else "?"
            # check_type picks which dimension(s) this evidence should count
            # toward â€” label it accordingly so the rubric model attributes
            # it correctly. "combined" (the current default) tests both
            # Transfer and Constraint Awareness in one question; "transfer"/
            # "constraint" are older single-dimension checks, still handled
            # for any already-generated reports referencing one.
            check_type = tc.get("check_type") or "transfer"
            if check_type == "combined":
                label = (
                    "TRANSFER + CONSTRAINT-AWARENESS CHECK — a single objectively-graded "
                    "multiple-choice question that requires BOTH applying the idea to a new "
                    "situation the student hadn't already discussed AND recognizing whether a "
                    "specific factor or condition changes the outcome in that situation. Use "
                    "this as evidence for both the Transfer and Constraint Awareness dimensions"
                )
            elif check_type == "constraint":
                label = (
                    "CONSTRAINT-AWARENESS CHECK — a separate, objectively-graded multiple-choice "
                    "question testing whether the student recognizes a limiting factor, assumption, "
                    "or condition that could change the answer"
                )
            else:
                label = (
                    "TRANSFER CHECK — a separate, objectively-graded multiple-choice question "
                    "applying the idea to a NEW situation the student hadn't already discussed"
                )
            transcript_text += (
                f"\n\n[{label}]\n"
                f"Question: {tc.get('question', '')}\n"
                f"Student answered: \"{chosen_text}\" — "
                f"{'CORRECT' if tc['status'] == 'correct' else 'INCORRECT'} "
                f"(correct answer: \"{correct_text}\")\n"
                f"{tc.get('explanation', '')}"
            )

        user_prompt = _build_user_prompt(
            transcript_text,
            row["concept_title"] or row["topic"] or "this concept",
            row["concept_subject"],
            row["course_grade"],
        )

        # This report is teacher-facing, so it belongs in the TEACHER's own
        # language, not the student's — a teacher who doesn't read the
        # student's language would otherwise get back an unreadable report,
        # since the model had no explicit instruction and would just mirror
        # whatever language the transcript happened to be in. The enum-like
        # fields (level/confidence/support_level) must stay in fixed English
        # values regardless — the frontend matches on those exact strings
        # for pill colors and trend ranking, so translating them would
        # silently break that.
        system_prompt = _REPORT_SYSTEM_PROMPT
        teacher_language = row["teacher_language"]
        if teacher_language in _LANGUAGE_NAMES:
            system_prompt += (
                f"\n\nIMPORTANT: Write every free-text field in {_LANGUAGE_NAMES[teacher_language]} — "
                "academic_understanding.summary, every dimension's description/observable_evidence/"
                "next_growth_step, strengths, areas_for_growth, next_steps, teacher_insight, "
                "suggested_next_topic, and optional_extension. Do not use English for these. "
                "However, keep level, confidence, and support_level values exactly as one of the "
                "fixed English options listed above — never translate those."
            )

        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        report_json = json.loads(response.choices[0].message.content)

        async with get_db() as db:
            await db.execute("""
                UPDATE ladder_session_reports
                SET report = $2::jsonb, status = 'ready', updated_at = NOW()
                WHERE id = $1::uuid
            """, report_id, json.dumps(report_json))

    except Exception as exc:
        logger.error(f"[ladder_report] failed for report {report_id}: {exc}")
        try:
            async with get_db() as db:
                await db.execute("""
                    UPDATE ladder_session_reports
                    SET status = 'failed', error_message = $2, updated_at = NOW()
                    WHERE id = $1::uuid
                """, report_id, str(exc)[:500])
        except Exception:
            pass  # never let report-generation failure raise anywhere
