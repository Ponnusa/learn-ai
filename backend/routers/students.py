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
