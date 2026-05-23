"""
Student skill scoring system.
Scores move based on quiz performance, conversation signals, and session quality.
All updates are additive — stored in student_profiles.skill_scores JSONB.
"""
import json
from database import get_db

SCORE_RULES = {
    "quiz_correct":           +3,
    "quiz_wrong":             -1,
    "quiz_perfect":           +5,   # bonus for 100%
    "quiz_repeated_wrong":    -3,   # same question wrong twice
    "follow_up_question":     +1,
    "simplify_requested":     -2,
    "go_deeper_requested":    +2,
    "example_requested":      -1,
    "video_completed":        +1,
    "video_abandoned":        -1,
    "long_productive_session":+3,
    "quick_exit":             -1,
}

INITIAL_SCORES = {
    "beginner":     15,
    "intermediate": 50,
    "advanced":     78,
}

SCORE_MIN, SCORE_MAX = 0, 100


async def get_score(user_id: str, subject: str) -> int:
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT skill_scores FROM student_profiles WHERE user_id = $1", user_id
        )
    if not row:
        return 50
    scores = row["skill_scores"] or {}
    return scores.get(subject, 50)


async def apply_delta(user_id: str, subject: str, delta: int, reason: str):
    """Apply a score delta and record history. Clamps to 0-100."""
    if delta == 0:
        return
    async with get_db() as db:
        # Upsert profile row if missing
        await db.execute("""
            INSERT INTO student_profiles (user_id) VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id)

        # Read current score
        row = await db.fetchrow(
            "SELECT skill_scores FROM student_profiles WHERE user_id = $1", user_id
        )
        scores = dict(row["skill_scores"] or {})
        old = scores.get(subject, 50)
        new = max(SCORE_MIN, min(SCORE_MAX, old + delta))
        scores[subject] = new

        await db.execute("""
            UPDATE student_profiles
            SET skill_scores = $1::jsonb, last_updated = NOW()
            WHERE user_id = $2
        """, json.dumps(scores), user_id)

        await db.execute("""
            INSERT INTO skill_score_history (user_id, subject, score, delta, reason)
            VALUES ($1, $2, $3, $4, $5)
        """, user_id, subject, new, delta, reason)


async def score_quiz_result(user_id: str, subject: str, correct: int, total: int):
    """Score a completed quiz."""
    if total == 0:
        return
    pct = correct / total
    if pct == 1.0:
        delta = SCORE_RULES["quiz_perfect"]
    else:
        delta = (correct * SCORE_RULES["quiz_correct"]) + ((total - correct) * SCORE_RULES["quiz_wrong"])
    await apply_delta(user_id, subject, delta, "quiz_completed")


async def score_signal(user_id: str, subject: str, signal: str):
    """Score a single behavioral signal."""
    delta = SCORE_RULES.get(signal, 0)
    if delta:
        await apply_delta(user_id, subject, delta, signal)


async def init_profile(user_id: str, knowledge_level: str):
    """Create initial profile when user signs up."""
    initial_score = INITIAL_SCORES.get(knowledge_level, 50)
    async with get_db() as db:
        await db.execute("""
            INSERT INTO student_profiles (user_id, skill_scores)
            VALUES ($1, $2::jsonb)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, json.dumps({"General": initial_score}))
