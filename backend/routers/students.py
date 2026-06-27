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
                   scp.visited, scp.quiz_score
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

    courses: dict[str, dict] = {}
    for r in rows:
        cid = str(r["course_id"])
        if cid not in courses:
            courses[cid] = {"id": cid, "name": r["course_name"], "concepts": []}
        courses[cid]["concepts"].append({
            "id":         str(r["concept_id"]),
            "title":      r["concept_title"],
            "visited":    bool(r["visited"]),
            "quiz_score": r["quiz_score"],
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
