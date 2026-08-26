"""
Background AI profile updater.
Runs after every 5 messages or quiz completion.
Uses gpt-4o-mini — cheap, non-blocking, never affects response speed.
AI rewrites the prompt_modifier based on observed student behaviour.
"""
import json
import asyncio
from database import get_db
from services.ai_router import openai_client, get_model
from services.scoring import apply_delta

_PROFILE_LANGUAGE_NAMES = {'fi': 'Finnish', 'sv': 'Swedish', 'es': 'Spanish', 'fr': 'French', 'no': 'Norwegian'}

PROFILE_UPDATE_PROMPT = """\
You are an educational intelligence system analysing a student's learning session.
Update their personalised AI tutor profile based on the evidence below.

CURRENT PROFILE:
Skill score in {subject}: {score}/100
Learning style: {learning_style}
Known misconceptions: {misconceptions}
Current prompt modifier: "{current_modifier}"

RECENT SESSION ({n_msgs} messages):
{conversation_summary}

QUIZ RESULTS (if any):
{quiz_results}

BEHAVIOURAL SIGNALS:
- Simplify requests: {simplify_count}
- Go-deeper requests: {deeper_count}
- Follow-up questions asked: {followup_count}

TASK: Return JSON with ONLY fields that should change.
null means no change. Be conservative — only update with clear evidence.

{{
  "skill_score_delta": 0,
  "learning_style": null,
  "vocab_level": null,
  "explanation_depth": null,
  "add_misconceptions": [],
  "resolve_misconceptions": [],
  "add_mastered": [],
  "add_struggles": [],
  "prompt_modifier": null
}}

For prompt_modifier: write 2-4 sentences of direct instruction for the AI tutor.
What works for this student? What to avoid? What to reinforce?
Write the prompt_modifier in {language_name}.
Example: "Explain with sports analogies first. Reinforce the difference between
force and energy proactively. Prefer step-by-step builds over top-down explanations."
"""


async def update_student_profile(
    user_id: str,
    conversation_id: str,
    subject: str,
    quiz_results: dict | None = None,
):
    """
    Background task — fire-and-forget.
    Never raises exceptions upward. Never slows the main response.
    """
    try:
        async with get_db() as db:
            msgs = await db.fetch("""
                SELECT role, content FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at DESC LIMIT 10
            """, conversation_id)

            profile = await db.fetchrow(
                "SELECT * FROM student_profiles WHERE user_id = $1", user_id
            )
            lang_val = await db.fetchval("SELECT language FROM users WHERE id = $1", user_id)

        language_name = _PROFILE_LANGUAGE_NAMES.get(lang_val or 'en', 'English')

        if not msgs:
            return

        conversation_summary = "\n".join(
            f"{m['role'].upper()}: {m['content'][:200]}" for m in reversed(msgs)
        )

        score = 50
        learning_style = "balanced"
        misconceptions = []
        current_modifier = ""
        simplify_count = 0
        deeper_count = 0

        if profile:
            score = (profile["skill_scores"] or {}).get(subject, 50)
            learning_style = profile["learning_style"] or "balanced"
            misconceptions = profile["known_misconceptions"] or []
            current_modifier = profile["prompt_modifier"] or ""
            simplify_count = profile["simplify_requests"] or 0
            deeper_count = profile["deeper_requests"] or 0

        followup_count = sum(1 for m in msgs if m["role"] == "user")

        resp = await openai_client.chat.completions.create(
            model=get_model("profile_update"),
            messages=[{
                "role": "user",
                "content": PROFILE_UPDATE_PROMPT.format(
                    subject=subject,
                    score=score,
                    learning_style=learning_style,
                    misconceptions=json.dumps(misconceptions),
                    current_modifier=current_modifier,
                    n_msgs=len(msgs),
                    conversation_summary=conversation_summary,
                    quiz_results=json.dumps(quiz_results or {}),
                    simplify_count=simplify_count,
                    deeper_count=deeper_count,
                    followup_count=followup_count,
                    language_name=language_name,
                ),
            }],
            max_tokens=400,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        delta = json.loads(resp.choices[0].message.content)
        await _apply_profile_delta(user_id, subject, delta)

    except Exception:
        pass  # profile update never breaks anything


async def _apply_profile_delta(user_id: str, subject: str, delta: dict):
    if not delta:
        return

    score_delta = delta.get("skill_score_delta", 0) or 0
    if score_delta:
        await apply_delta(user_id, subject, score_delta, "session_analysis")

    async with get_db() as db:
        profile = await db.fetchrow(
            "SELECT * FROM student_profiles WHERE user_id = $1", user_id
        )
        if not profile:
            await db.execute(
                "INSERT INTO student_profiles (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id
            )
            profile = await db.fetchrow(
                "SELECT * FROM student_profiles WHERE user_id = $1", user_id
            )

        misconceptions = list(profile["known_misconceptions"] or [])
        mastered = list(profile["mastered_concepts"] or [])
        struggles = list(profile["struggle_areas"] or [])

        for m in delta.get("add_misconceptions", []) or []:
            if m and m not in misconceptions:
                misconceptions.append(m)
        for m in delta.get("resolve_misconceptions", []) or []:
            if m in misconceptions:
                misconceptions.remove(m)
        for m in delta.get("add_mastered", []) or []:
            if m and m not in mastered:
                mastered.append(m)
        for s in delta.get("add_struggles", []) or []:
            if s and s not in struggles:
                struggles.append(s)

        updates = {
            "known_misconceptions": json.dumps(misconceptions),
            "mastered_concepts":    json.dumps(mastered),
            "struggle_areas":       json.dumps(struggles),
            "last_updated":         "NOW()",
            "profile_version":      (profile["profile_version"] or 1) + 1,
        }

        if delta.get("learning_style"):
            updates["learning_style"] = delta["learning_style"]
        if delta.get("vocab_level"):
            updates["vocab_level"] = delta["vocab_level"]
        if delta.get("explanation_depth"):
            updates["explanation_depth"] = delta["explanation_depth"]
        if delta.get("prompt_modifier"):
            updates["prompt_modifier"] = delta["prompt_modifier"]

        await db.execute("""
            UPDATE student_profiles SET
              known_misconceptions = $1::jsonb,
              mastered_concepts    = $2::jsonb,
              struggle_areas       = $3::jsonb,
              profile_version      = $4,
              last_updated         = NOW(),
              learning_style       = COALESCE($5, learning_style),
              vocab_level          = COALESCE($6, vocab_level),
              explanation_depth    = COALESCE($7, explanation_depth),
              prompt_modifier      = COALESCE($8, prompt_modifier)
            WHERE user_id = $9
        """,
            json.dumps(misconceptions),
            json.dumps(mastered),
            json.dumps(struggles),
            updates["profile_version"],
            delta.get("learning_style"),
            delta.get("vocab_level"),
            delta.get("explanation_depth"),
            delta.get("prompt_modifier"),
            user_id,
        )
