"""
Quiz router — generate adaptive quizzes, submit answers, score results.
Same quiz generation prompt as AnimLearn.
"""
import json
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from database import get_db
from services.ai_router import openai_client, get_model
from services.prompt_builder import QUIZ_GENERATION_PROMPT
from services.tier_config import get_limit
from services.scoring import score_quiz_result, get_score

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


class QuizRequest(BaseModel):
    topic: str
    conversation_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    subject: str | None = None
    language: str = "en"
    num_questions: int | None = None   # None = use tier default


class SubmitRequest(BaseModel):
    answers: dict   # {question_index: selected_option}
    user_id: str | None = None


@router.post("/generate")
async def generate_quiz(req: QuizRequest):
    # ── Credit check ─────────────────────────────────────────────────────────
    tier = "anonymous"
    if req.user_id:
        async with get_db() as db:
            user = await db.fetchrow("SELECT tier FROM users WHERE id = $1", req.user_id)
        tier = user["tier"] if user else "free"
    await _check_quiz_credit(req.user_id, req.session_id, tier)

    # ── Determine number of questions based on tier ───────────────────────────
    max_q = await get_limit(tier, "quiz_questions_max")
    n_questions = min(req.num_questions or max_q, max_q)

    # ── Adapt difficulty from student score ───────────────────────────────────
    difficulty = "mixed"
    if req.user_id and req.subject:
        score = await get_score(req.user_id, req.subject)
        if score < 35:
            difficulty = "easy"
        elif score < 65:
            difficulty = "medium"
        else:
            difficulty = "hard — include edge cases and deeper reasoning"

    # ── Generate questions (same prompt as AnimLearn) ─────────────────────────
    prompt = (
        f"{QUIZ_GENERATION_PROMPT}\n\n"
        f"Topic: {req.topic}\n"
        f"Number of questions: {n_questions}\n"
        f"Difficulty: {difficulty}\n"
        f"Language: {req.language}\n\n"
        "Return a JSON object: {\"questions\": [...]}\n"
        "Each question: {\"q\": str, \"options\": [str x4], \"correct\": 0-3, \"explanation\": str, \"difficulty\": str}"
    )

    resp = await openai_client.chat.completions.create(
        model=get_model("quiz_generation"),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    questions = data.get("questions", [])[:n_questions]

    # ── Save quiz + credit (must succeed — quiz doesn't exist until this runs) ──
    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO quizzes (conversation_id, user_id, session_id, subject, questions)
            VALUES ($1,$2,$3,$4,$5::jsonb) RETURNING id
        """, req.conversation_id, req.user_id, req.session_id, req.subject,
            json.dumps(questions))

        quiz_id = str(row["id"])

        # Record credit AFTER successful generation (not before)
        if req.user_id:
            await db.execute(
                "INSERT INTO usage_events (user_id, event_type) VALUES ($1, 'quiz_taken')",
                req.user_id,
            )
        elif req.session_id:
            await db.execute(
                "UPDATE anonymous_sessions SET quiz_count = quiz_count + 1 WHERE id = $1",
                req.session_id,
            )

    # ── Save quiz-card message (non-critical — a failure here must NOT 500) ───
    quiz_msg_id = None
    if req.conversation_id:
        try:
            display_topic = req.subject or req.topic[:60]
            async with get_db() as db:
                msg_row = await db.fetchrow("""
                    INSERT INTO messages (conversation_id, role, content, metadata)
                    VALUES ($1, 'assistant', $2, $3::jsonb) RETURNING id
                """, req.conversation_id,
                    f"Quiz: {display_topic}",
                    json.dumps({
                        "quiz_id":       quiz_id,
                        "quiz_topic":    display_topic,
                        "num_questions": len(questions),
                    }))
            quiz_msg_id = str(msg_row["id"])
        except Exception:
            pass  # quiz still works; card just won't persist in chat history

    return {"quiz_id": quiz_id, "questions": questions, "message_id": quiz_msg_id}


@router.get("/{quiz_id}")
async def get_quiz(quiz_id: str):
    """Fetch quiz questions + completion status by ID."""
    async with get_db() as db:
        quiz = await db.fetchrow(
            "SELECT id, questions, subject, completed_at, score, max_score, user_answers FROM quizzes WHERE id = $1",
            quiz_id,
        )
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    def _unwrap(v):
        """If asyncpg decoded a double-encoded JSONB string, unwrap one level."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return v
        return v

    return {
        "quiz_id":      str(quiz["id"]),
        "questions":    _unwrap(quiz["questions"]),
        "subject":      quiz["subject"],
        "completed":    quiz["completed_at"] is not None,
        "score":        quiz["score"],
        "max_score":    quiz["max_score"],
        "user_answers": _unwrap(quiz["user_answers"]) or {},
    }


@router.post("/{quiz_id}/submit")
async def submit_quiz(quiz_id: str, req: SubmitRequest, bg: BackgroundTasks):
    async with get_db() as db:
        quiz = await db.fetchrow(
            "SELECT * FROM quizzes WHERE id = $1", quiz_id
        )
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = quiz["questions"]
    correct = sum(
        1 for i, q in enumerate(questions)
        if req.answers.get(str(i)) == q["correct"]
    )
    total = len(questions)
    score_pct = round((correct / total) * 100) if total else 0

    # Detailed results with explanations
    results = []
    for i, q in enumerate(questions):
        user_ans = req.answers.get(str(i))
        results.append({
            "question":     q["q"],
            "options":      q["options"],
            "correct":      q["correct"],
            "user_answer":  user_ans,
            "is_correct":   user_ans == q["correct"],
            "explanation":  q.get("explanation", ""),
        })

    async with get_db() as db:
        await db.execute("""
            UPDATE quizzes
            SET user_answers = $1::jsonb, score = $2, max_score = $3, completed_at = NOW()
            WHERE id = $4
        """, json.dumps(req.answers), correct, total, quiz_id)

    # Score the student profile in background
    if req.user_id and quiz["subject"]:
        bg.add_task(score_quiz_result, req.user_id, quiz["subject"], correct, total)

    return {
        "correct":   correct,
        "total":     total,
        "score_pct": score_pct,
        "results":   results,
        "passed":    score_pct >= 70,
    }


async def _check_quiz_credit(user_id: str | None, session_id: str | None, tier: str):
    async with get_db() as db:
        if user_id:
            limit = await get_limit(tier, "quiz_daily")
            if limit == -1:
                return
            count = await db.fetchval("""
                SELECT COUNT(*) FROM usage_events
                WHERE user_id = $1 AND event_type = 'quiz_taken'
                AND created_at > NOW() - INTERVAL '1 day'
            """, user_id)
            if count >= limit:
                raise HTTPException(status_code=429, detail="Daily quiz limit reached")
            # INSERT moved to generate_quiz (after successful generation)
        elif session_id:
            row = await db.fetchrow(
                "SELECT quiz_count FROM anonymous_sessions WHERE id = $1", session_id
            )
            limit = await get_limit("anonymous", "quiz_total")
            if row and row["quiz_count"] >= limit:
                raise HTTPException(status_code=429, detail="session_limit_reached")
