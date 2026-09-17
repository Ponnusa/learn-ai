"""
Student detail router — teacher-facing views of a single student:
  GET /api/students/{id}/progress               — cross-course progress breakdown
  GET /api/students/{id}/profile                — AI-tutor learning profile (Part B)
  GET /api/students/{id}/conversations           — read-only AI-tutor chat feed (Part B)
  GET /api/students/{id}/courses/{cid}/summary   — complete result: quant roll-up +
                                                     Thinking Radar rollup + AI narrative
"""
import json
import logging
from collections import Counter

from fastapi import APIRouter, HTTPException, Header

from database import get_db
from routers.courses import _require_teacher
from services.ai_router import openai_client
from services.ladder_report import REPORT_DIMENSIONS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/students", tags=["students"])

_LEVEL_RANK = {"Limited Evidence": 0, "Beginner": 1, "Developing": 2, "Proficient": 3, "Advanced": 4}
_DIMENSION_LABELS = {
    "decision_making":      "Decision-Making",
    "justification":        "Justification",
    "constraint_awareness": "Constraint Awareness",
    "transfer":              "Transfer",
}


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

        # Video block totals per concept (textbook blocks only)
        video_block_total_rows = await db.fetch("""
            SELECT concept_id, COUNT(*) AS total
            FROM concept_content_blocks
            WHERE type = 'video' AND in_textbook = true
            GROUP BY concept_id
        """)

        # How many video blocks this student has watched ≥ 75 %
        video_watched_rows = await db.fetch("""
            SELECT concept_id, COUNT(*) AS watched
            FROM concept_video_watches
            WHERE student_id = $1::uuid
              AND pct_watched >= 75
              AND block_id != 'legacy'
            GROUP BY concept_id
        """, student_id)

        # Most recent quiz attempt's per-question answers per concept
        last_answer_rows = await db.fetch("""
            SELECT DISTINCT ON (concept_id) concept_id, answers
            FROM concept_quiz_attempts
            WHERE student_id = $1::uuid AND answers IS NOT NULL
            ORDER BY concept_id, taken_at DESC
        """, student_id)

        # Verified guided-discovery (ladder) chains resolved per concept —
        # only chains that passed the transfer-check gate, not merely ones
        # the tutor itself decided were "done".
        guided_rows = await db.fetch("""
            SELECT cc.id AS concept_id, COUNT(*) AS resolved_count, AVG(gde.steps) AS avg_steps
            FROM guided_discovery_events gde
            JOIN conversations c    ON c.id = gde.conversation_id
            JOIN course_concepts cc ON cc.study_set_id = c.study_set_id
            WHERE gde.user_id = $1::uuid
            GROUP BY cc.id
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
    video_total_map: dict[str, int]   = {str(r["concept_id"]): int(r["total"])   for r in video_block_total_rows}
    video_watched_map: dict[str, int] = {str(r["concept_id"]): int(r["watched"]) for r in video_watched_rows}
    last_answers_map: dict[str, list] = {str(r["concept_id"]): r["answers"] for r in last_answer_rows}
    guided_map: dict[str, dict] = {
        str(r["concept_id"]): {"resolved_count": int(r["resolved_count"]), "avg_steps": round(float(r["avg_steps"]), 1)}
        for r in guided_rows
    }

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
            "ai_msg_count":          ai_map.get(cpt_id, 0),
            "quiz_attempts":         attempt_map.get(cpt_id, []),
            "time_spent_seconds":    time_map.get(cpt_id, 0),
            "video_blocks_total":    video_total_map.get(cpt_id, 0),
            "video_blocks_watched":  video_watched_map.get(cpt_id, 0),
            "last_attempt_answers":  last_answers_map.get(cpt_id),
            "guided_resolved_count": guided_map.get(cpt_id, {}).get("resolved_count", 0),
            "guided_avg_steps":      guided_map.get(cpt_id, {}).get("avg_steps"),
        })

    return {
        "id":      str(student["id"]),
        "name":    student["name"],
        "email":   student["email"],
        "courses": list(courses.values()),
    }


@router.get("/{student_id}/concepts/{concept_id}/quiz-history")
async def get_student_quiz_history(student_id: str, concept_id: str, authorization: str = Header(...)):
    """
    Teacher-only. Full attempt history for one student × concept, including per-question
    answers so the teacher can see exactly which questions the student got wrong.
    """
    await _require_teacher_of_student(authorization, student_id)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, score, answers, taken_at
            FROM concept_quiz_attempts
            WHERE student_id = $1::uuid AND concept_id = $2::uuid
            ORDER BY taken_at ASC
        """, student_id, concept_id)
    return [
        {
            "id":       str(r["id"]),
            "score":    round(r["score"]),
            "answers":  r["answers"],
            "taken_at": r["taken_at"].isoformat() if r["taken_at"] else None,
        }
        for r in rows
    ]


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


def _rollup_levels(levels: list[str]) -> dict:
    """
    Most-common level + a simple first-half-vs-second-half trend from an
    ordered (oldest-first) list of level strings. Pure code, no AI call —
    the levels are already an enum-like small set, so a mode + ordinal-rank
    comparison is exact and instant rather than something worth asking a
    model to eyeball.
    """
    if not levels:
        return {"most_common": None, "trend": "insufficient", "session_count": 0}
    most_common = Counter(levels).most_common(1)[0][0]
    if len(levels) < 2:
        return {"most_common": most_common, "trend": "insufficient", "session_count": len(levels)}
    ranks = [_LEVEL_RANK.get(l, 0) for l in levels]
    mid = len(ranks) // 2 or 1
    first_avg  = sum(ranks[:mid]) / mid
    second_avg = sum(ranks[mid:]) / (len(ranks) - mid)
    if second_avg - first_avg >= 0.5:   trend = "up"
    elif first_avg - second_avg >= 0.5: trend = "down"
    else:                                trend = "flat"
    return {"most_common": most_common, "trend": trend, "session_count": len(levels)}


@router.get("/{student_id}/courses/{course_id}/summary")
async def get_student_course_summary(student_id: str, course_id: str, authorization: str = Header(...)):
    """
    "Complete result" for a student in one course, combining three layers:
      1. Quantitative roll-up (visited/quiz/mastery/guided-discovery stats)
         — pure aggregation of data already tracked elsewhere, no AI cost.
      2. Deterministic Thinking Radar rollup across every resolved ladder
         session report for this student in this course (most-common level
         + trend per dimension) — also no AI cost, the reports are already
         structured JSON.
      3. A short AI-written narrative synthesizing the trajectory across
         those same reports. Cached in student_course_narratives and only
         regenerated when report_count no longer matches — a new session
         resolved since it was last written.
    """
    teacher_id = await _require_teacher_of_student(authorization, student_id)

    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id, name FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        if not course:
            raise HTTPException(404, "Course not found")
        student = await db.fetchrow("SELECT id, name FROM users WHERE id = $1::uuid", student_id)

        # A verified guided-discovery resolution counts toward "Mastered"
        # here too, same rule already applied to the progress-grid's
        # getMastery() on the frontend (a passed transfer-check is at least
        # as strong a signal as a quiz score) â€” this endpoint's own
        # mastered_count had been left checking quiz_score alone, which is
        # why it could show 0 even with real guided-discovery activity.
        stats = await db.fetchrow("""
            SELECT
                COUNT(cc.id)                                                     AS total_concepts,
                COUNT(*) FILTER (WHERE scp.visited)                             AS visited_count,
                AVG(scp.quiz_score) FILTER (WHERE scp.quiz_score IS NOT NULL)     AS avg_quiz_score,
                COUNT(*) FILTER (
                    WHERE scp.visited AND (scp.quiz_score >= 70 OR gc.resolved_count > 0)
                )                                                                AS mastered_count,
                MAX(scp.last_seen_at)                                           AS last_active
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            LEFT JOIN student_concept_progress scp
                   ON scp.concept_id = cc.id AND scp.student_id = $1::uuid
            LEFT JOIN (
                SELECT cc2.id AS concept_id, COUNT(*) AS resolved_count
                FROM guided_discovery_events gde
                JOIN conversations c     ON c.id = gde.conversation_id
                JOIN course_concepts cc2 ON cc2.study_set_id = c.study_set_id
                WHERE gde.user_id = $1::uuid
                GROUP BY cc2.id
            ) gc ON gc.concept_id = cc.id
            WHERE cu.course_id = $2::uuid
        """, student_id, course_id)

        guided = await db.fetchrow("""
            SELECT COUNT(*) AS resolved_total, AVG(gde.steps) AS avg_steps
            FROM guided_discovery_events gde
            JOIN conversations c    ON c.id = gde.conversation_id
            JOIN course_concepts cc ON cc.study_set_id = c.study_set_id
            JOIN course_units cu    ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid AND gde.user_id = $2::uuid
        """, course_id, student_id)

        report_rows = await db.fetch("""
            SELECT lsr.report, lsr.created_at, cc.title AS concept_title
            FROM ladder_session_reports lsr
            JOIN course_concepts cc ON cc.id = lsr.concept_id
            JOIN course_units cu    ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid AND lsr.student_id = $2::uuid AND lsr.status = 'ready'
            ORDER BY lsr.created_at ASC
        """, course_id, student_id)

        cached_narrative = await db.fetchrow("""
            SELECT narrative, report_count, updated_at
            FROM student_course_narratives
            WHERE student_id = $1::uuid AND course_id = $2::uuid
        """, student_id, course_id)

    reports = []
    for r in report_rows:
        rep = r["report"]
        if isinstance(rep, str):
            try:    rep = json.loads(rep)
            except: rep = None
        if rep:
            reports.append({"report": rep, "created_at": r["created_at"], "concept_title": r["concept_title"]})

    # ── Layer 2: deterministic Thinking Radar rollup ─────────────────────
    academic_levels = [
        r["report"]["academic_understanding"]["level"] for r in reports
        if r["report"].get("academic_understanding", {}).get("level")
    ]
    dim_rollups = {}
    for dim in REPORT_DIMENSIONS:
        levels = [
            r["report"]["thinking_radar"][dim]["level"] for r in reports
            if r["report"].get("thinking_radar", {}).get(dim, {}).get("level")
        ]
        dim_rollups[dim] = _rollup_levels(levels)

    weakest = min(
        (d for d in dim_rollups if dim_rollups[d]["most_common"] is not None),
        key=lambda d: _LEVEL_RANK.get(dim_rollups[d]["most_common"], 0),
        default=None,
    )
    layer2 = {
        "academic_understanding": _rollup_levels(academic_levels),
        "thinking_radar": dim_rollups,
        "focus_recommendation": _DIMENSION_LABELS.get(weakest) if weakest else None,
    }

    # ── Layer 3: AI narrative, cached until a new report lands ───────────
    layer3 = None
    if reports:
        if cached_narrative and cached_narrative["report_count"] == len(reports):
            layer3 = {
                "narrative":    cached_narrative["narrative"],
                "updated_at":   cached_narrative["updated_at"].isoformat(),
                "report_count": cached_narrative["report_count"],
            }
        else:
            session_lines = []
            for i, r in enumerate(reports, 1):
                rep = r["report"]
                radar = rep.get("thinking_radar", {})
                dims_line = ", ".join(
                    f"{_DIMENSION_LABELS[d]}: {radar.get(d, {}).get('level', '?')}" for d in REPORT_DIMENSIONS
                )
                date_str = r["created_at"].date().isoformat() if r["created_at"] else "?"
                au_level = rep.get("academic_understanding", {}).get("level", "?")
                session_lines.append(
                    f"{i}. {r['concept_title']} ({date_str}) — Academic Understanding: {au_level}. {dims_line}."
                )
            user_prompt = (
                f"STUDENT: {student['name']}\nCOURSE: {course['name']}\n\n"
                f"SESSIONS (chronological, oldest first):\n" + "\n".join(session_lines)
            )
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": (
                        "You are an expert learning-progress analyst writing a short course-level "
                        "summary for a teacher, synthesizing several already rubric-scored tutoring "
                        "sessions for one student in one course. Write 3-5 sentences, warm but "
                        "precise, referencing concrete trends across sessions rather than restating "
                        "each one individually. End with the single most useful thing for the "
                        "teacher to know going forward."
                    )},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=400,
                temperature=0.4,
            )
            narrative_text = (response.choices[0].message.content or "").strip()
            async with get_db() as db:
                await db.execute("""
                    INSERT INTO student_course_narratives (student_id, course_id, narrative, report_count)
                    VALUES ($1::uuid, $2::uuid, $3, $4)
                    ON CONFLICT (student_id, course_id) DO UPDATE
                    SET narrative = EXCLUDED.narrative, report_count = EXCLUDED.report_count, updated_at = NOW()
                """, student_id, course_id, narrative_text, len(reports))
            layer3 = {"narrative": narrative_text, "updated_at": None, "report_count": len(reports)}

    return {
        "layer1": {
            "total_concepts":        stats["total_concepts"],
            "visited_count":         stats["visited_count"],
            "avg_quiz_score":        round(stats["avg_quiz_score"], 1) if stats["avg_quiz_score"] is not None else None,
            "mastered_count":        stats["mastered_count"],
            "guided_resolved_count": guided["resolved_total"] or 0,
            "guided_avg_steps":      round(float(guided["avg_steps"]), 1) if guided["avg_steps"] is not None else None,
            "last_active":           stats["last_active"].isoformat() if stats["last_active"] else None,
        },
        "layer2": layer2,
        "layer3": layer3,
    }
