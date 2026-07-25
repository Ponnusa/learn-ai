"""
Student detail router — teacher-facing views of a single student:
  GET /api/students/{id}/progress       — cross-course progress breakdown
  GET /api/students/{id}/profile        — AI-tutor learning profile (Part B)
  GET /api/students/{id}/conversations  — read-only AI-tutor chat feed (Part B)
"""
import logging
from fastapi import APIRouter, HTTPException, Header

from database import get_db
from routers.courses import _require_teacher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/students", tags=["students"])


async def _require_teacher_of_student(authorization: str, student_id: str) -> str:
    """Teacher auth + verifies this student is enrolled in one of the caller's classrooms."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        enrolled = await db.fetchval("""
            SELECT 1 FROM classroom_students cs
            JOIN classrooms cl ON cl.id = cs.classroom_id
            WHERE cl.teacher_id = $1::uuid AND cs.student_id = $2::uuid
            LIMIT 1
        """, teacher_id, student_id)
    if not enrolled:
        raise HTTPException(403, "Student not in one of your classrooms")
    return teacher_id


@router.get("/{student_id}/progress")
async def get_student_progress(student_id: str, authorization: str = Header(...)):
    """Every concept (across all of this teacher's courses the student can see), with visited/quiz_score."""
    teacher_id = await _require_teacher_of_student(authorization, student_id)

    async with get_db() as db:
        student = await db.fetchrow(
            "SELECT id, name, email FROM users WHERE id = $1::uuid", student_id
        )
        if not student:
            raise HTTPException(404, "Student not found")

        rows = await db.fetch("""
            SELECT DISTINCT c.id AS course_id, c.name AS course_name, c.created_at AS course_created_at,
                   cu.position AS unit_position,
                   cc.id AS concept_id, cc.title AS concept_title, cc.position AS concept_position,
                   scp.visited, scp.quiz_score, scp.last_seen_at
            FROM classroom_students cs
            JOIN classrooms cl         ON cl.id = cs.classroom_id AND cl.teacher_id = $2::uuid
            JOIN classroom_courses clc ON clc.classroom_id = cl.id
            JOIN courses c             ON c.id = clc.course_id
            JOIN course_units cu       ON cu.course_id = c.id
            JOIN course_concepts cc    ON cc.unit_id = cu.id
            LEFT JOIN student_concept_progress scp
                   ON scp.concept_id = cc.id AND scp.student_id = cs.student_id
            WHERE cs.student_id = $1::uuid
            ORDER BY c.created_at, cu.position, cc.position
        """, student_id, teacher_id)

        # Flashcard mastery per concept for this student
        fc_rows = await db.fetch("""
            WITH latest AS (
                SELECT DISTINCT ON (cfr.flashcard_id)
                       cf.concept_id, cfr.rating
                FROM concept_flashcard_reviews cfr
                JOIN concept_flashcards cf ON cf.id = cfr.flashcard_id
                WHERE cfr.student_id = $1::uuid
                ORDER BY cfr.flashcard_id, cfr.reviewed_at DESC
            ),
            totals AS (
                SELECT concept_id, COUNT(*) AS total FROM concept_flashcards
                GROUP BY concept_id
            )
            SELECT l.concept_id,
                   t.total                                    AS total_cards,
                   COUNT(*) FILTER (WHERE l.rating >= 3)     AS mastered_cards
            FROM latest l
            JOIN totals t ON t.concept_id = l.concept_id
            GROUP BY l.concept_id, t.total
        """, student_id)

        # AI messages asked about concepts (via conversations linked to this student)
        msg_count_rows = await db.fetch("""
            SELECT c.concept_id, COUNT(m.id) AS msg_count
            FROM conversations c
            JOIN messages m ON m.conversation_id = c.id AND m.role = 'user'
            WHERE c.user_id = $1::uuid AND c.concept_id IS NOT NULL
            GROUP BY c.concept_id
        """, student_id)

        # Quiz attempt history — up to 5 most recent per concept
        attempt_rows = await db.fetch("""
            SELECT concept_id, score, taken_at
            FROM concept_quiz_attempts
            WHERE student_id = $1::uuid
            ORDER BY concept_id, taken_at ASC
        """, student_id)

        # Total time spent per concept (sum across all days)
        time_rows = await db.fetch("""
            SELECT concept_id, SUM(seconds_spent) AS total_seconds
            FROM concept_time_logs
            WHERE student_id = $1::uuid
            GROUP BY concept_id
        """, student_id)

    fc_map: dict[str, dict] = {}
    for r in fc_rows:
        total    = int(r["total_cards"]   or 0)
        mastered = int(r["mastered_cards"] or 0)
        fc_map[str(r["concept_id"])] = {
            "flashcard_pct":      round(mastered / total * 100) if total > 0 else None,
            "flashcard_mastered": mastered,
            "flashcard_total":    total,
        }

    ai_map: dict[str, int] = {str(r["concept_id"]): int(r["msg_count"] or 0) for r in msg_count_rows}

    # Group attempts by concept, keep last 5
    attempt_map: dict[str, list] = {}
    for r in attempt_rows:
        cid = str(r["concept_id"])
        if cid not in attempt_map:
            attempt_map[cid] = []
        attempt_map[cid].append(round(r["score"]))
    for cid in attempt_map:
        attempt_map[cid] = attempt_map[cid][-5:]  # keep 5 most recent

    time_map: dict[str, int] = {str(r["concept_id"]): int(r["total_seconds"] or 0) for r in time_rows}

    courses: dict[str, dict] = {}
    for r in rows:
        cid = str(r["course_id"])
        if cid not in courses:
            courses[cid] = {"id": cid, "name": r["course_name"], "concepts": []}
        cpt_id = str(r["concept_id"])
        fc     = fc_map.get(cpt_id, {})
        ls     = r["last_seen_at"]
        courses[cid]["concepts"].append({
            "id":                 cpt_id,
            "title":              r["concept_title"],
            "visited":            bool(r["visited"]),
            "quiz_score":         r["quiz_score"],
            "last_seen_at":       ls.isoformat() if ls else None,
            "flashcard_pct":      fc.get("flashcard_pct"),
            "flashcard_mastered": fc.get("flashcard_mastered", 0),
            "flashcard_total":    fc.get("flashcard_total", 0),
            "ai_msg_count":       ai_map.get(cpt_id, 0),
            "quiz_attempts":      attempt_map.get(cpt_id, []),
            "time_spent_seconds": time_map.get(cpt_id, 0),
        })

    return {
        "id":      str(student["id"]),
        "name":    student["name"],
        "email":   student["email"],
        "courses": list(courses.values()),
    }


@router.get("/{student_id}/profile")
async def get_student_learning_profile(student_id: str, authorization: str = Header(...)):
    """
    AI-tutor-derived learning profile (services/profile_updater.py writes this after
    every 5 messages or a quiz). Returns a null-ish empty shape if the student hasn't
    chatted enough yet to have a profile row — not an error.
    """
    await _require_teacher_of_student(authorization, student_id)

    async with get_db() as db:
        profile = await db.fetchrow("""
            SELECT skill_scores, known_misconceptions, struggle_areas, mastered_concepts,
                   grade, goal, subject_confidence, avg_quiz_score, total_messages, last_updated
            FROM student_profiles WHERE user_id = $1::uuid
        """, student_id)

    if not profile:
        return {
            "has_profile": False, "skill_scores": {}, "known_misconceptions": [],
            "struggle_areas": [], "mastered_concepts": [], "grade": None, "goal": None,
            "subject_confidence": {}, "avg_quiz_score": None, "total_messages": 0, "last_updated": None,
        }

    return {
        "has_profile":           True,
        "skill_scores":          profile["skill_scores"] or {},
        "known_misconceptions":  profile["known_misconceptions"] or [],
        "struggle_areas":        profile["struggle_areas"] or [],
        "mastered_concepts":     profile["mastered_concepts"] or [],
        "grade":                 profile["grade"],
        "goal":                  profile["goal"],
        "subject_confidence":    profile["subject_confidence"] or {},
        "avg_quiz_score":        profile["avg_quiz_score"],
        "total_messages":        profile["total_messages"] or 0,
        "last_updated":          profile["last_updated"].isoformat() if profile["last_updated"] else None,
    }


@router.get("/{student_id}/conversations")
async def get_student_conversations(student_id: str, authorization: str = Header(...)):
    """Read-only feed of this student's full AI-tutor chat history (all subjects, all study sets)."""
    await _require_teacher_of_student(authorization, student_id)

    async with get_db() as db:
        rows = await db.fetch("""
            SELECT c.id, c.title, c.subject, c.created_at, c.updated_at,
                   COUNT(m.id) AS message_count, MAX(m.created_at) AS last_message_at
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.user_id = $1::uuid
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT 50
        """, student_id)

    return [
        {
            "id":              str(r["id"]),
            "title":           r["title"],
            "subject":         r["subject"],
            "message_count":   int(r["message_count"] or 0),
            "last_message_at": r["last_message_at"].isoformat() if r["last_message_at"] else None,
            "created_at":      r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.get("/{student_id}/conversations/{conversation_id}/messages")
async def get_student_conversation_messages(
    student_id: str, conversation_id: str, authorization: str = Header(...)
):
    """Read-only message list for one of this student's conversations."""
    await _require_teacher_of_student(authorization, student_id)

    async with get_db() as db:
        conv = await db.fetchrow(
            "SELECT id FROM conversations WHERE id = $1::uuid AND user_id = $2::uuid",
            conversation_id, student_id,
        )
        if not conv:
            raise HTTPException(404, "Conversation not found")

        rows = await db.fetch("""
            SELECT role, content, created_at FROM messages
            WHERE conversation_id = $1::uuid
            ORDER BY created_at ASC
        """, conversation_id)

    return [
        {"role": r["role"], "content": r["content"], "created_at": r["created_at"].isoformat() if r["created_at"] else None}
        for r in rows
    ]
