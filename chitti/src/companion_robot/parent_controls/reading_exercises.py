"""Parent-assigned reading exercises (decision 0052): a specific
passage for one child -- e.g. school homework -- kept separate from
both the shared `stories` library (Story Companion reads TO the
child) and Reading Partner's LLM-generated decodable books. Content
is trusted as-is (no safety screening), same reasoning risk register
#14 already applies to parent-uploaded stories and lullaby audio: the
parent is the authorizing adult for their own child.

Consumed exactly once as a NEW assignment: _run_reading_partner()
marks an exercise consumed as soon as it's picked up, so it's served
as "the next thing to read" only once, not every session. Decision
0068: a consumed exercise isn't gone for good, though -- a later
session offers to read it again (voice-driven, opt-in, asked once per
session), and the very next freshly-generated book after a first,
fresh read of one is themed as its follow-up (same topic/vocabulary),
both still falling back to the mode's usual adaptive generation once
neither applies.

Decision 0131: comprehension questions for an exercise are generated
up front, not live during the reading session -- see
parent_controls/comprehension_worker.py (a separate, headless process
that holds the LLM key; this Flask app never does) and Reading
Partner's own use of `comprehension_status == "approved"`.
`_COMPREHENSION_SEP` matches reading/repository.py's own
`_SIGHT_WORD_SEP` convention for a flat list-of-strings column.
"""
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from companion_robot.storage.migrations import run_migrations

_COMPREHENSION_SEP = "\x1f"


@dataclass
class ReadingExerciseRecord:
    id: str
    child_profile_id: str
    title: str
    content: str
    created_at: datetime
    consumed_at: datetime | None = None
    # Decision 0131: "pending" (not generated yet) -> "generated"
    # (worker produced questions, awaiting parent review) ->
    # "approved" (safe to use with the child) -- or "failed" (worker
    # tried and got nothing usable; a parent can request regeneration,
    # which resets this back to "pending").
    comprehension_status: str = "pending"
    comprehension_questions: list[str] = field(default_factory=list)
    comprehension_generated_at: datetime | None = None
    comprehension_approved_at: datetime | None = None


class ReadingExerciseRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, exercise: ReadingExerciseRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO reading_exercises (
                id, child_profile_id, title, content, created_at, consumed_at,
                comprehension_status, comprehension_questions,
                comprehension_generated_at, comprehension_approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exercise.id,
                exercise.child_profile_id,
                exercise.title,
                exercise.content,
                exercise.created_at.isoformat(),
                exercise.consumed_at.isoformat() if exercise.consumed_at else None,
                exercise.comprehension_status,
                _COMPREHENSION_SEP.join(exercise.comprehension_questions),
                exercise.comprehension_generated_at.isoformat()
                if exercise.comprehension_generated_at
                else None,
                exercise.comprehension_approved_at.isoformat()
                if exercise.comprehension_approved_at
                else None,
            ),
        )
        self._conn.commit()

    def list_for_child(self, child_profile_id: str) -> list[ReadingExerciseRecord]:
        rows = self._conn.execute(
            "SELECT * FROM reading_exercises WHERE child_profile_id = ? ORDER BY created_at",
            (child_profile_id,),
        ).fetchall()
        return [_row_to_exercise(row) for row in rows]

    def next_pending_for_child(self, child_profile_id: str) -> ReadingExerciseRecord | None:
        row = self._conn.execute(
            "SELECT * FROM reading_exercises WHERE child_profile_id = ? "
            "AND consumed_at IS NULL ORDER BY created_at LIMIT 1",
            (child_profile_id,),
        ).fetchone()
        return _row_to_exercise(row) if row else None

    def mark_consumed(self, exercise_id: str) -> None:
        self._conn.execute(
            "UPDATE reading_exercises SET consumed_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), exercise_id),
        )
        self._conn.commit()

    def delete(self, exercise_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM reading_exercises WHERE id = ?", (exercise_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # -- Decision 0131: comprehension-question generation/approval --------

    def list_awaiting_generation(self) -> list[ReadingExerciseRecord]:
        """Global across every child -- comprehension_worker.py is a
        single headless process polling the whole db, not scoped to
        one child the way Reading Partner's own reads are."""
        rows = self._conn.execute(
            "SELECT * FROM reading_exercises WHERE comprehension_status = 'pending' "
            "ORDER BY created_at"
        ).fetchall()
        return [_row_to_exercise(row) for row in rows]

    def save_generated_questions(self, exercise_id: str, questions: list[str]) -> None:
        """The worker's own result -- "generated," not "approved": a
        parent still has to review these before Reading Partner will
        ever use them with the child."""
        self._conn.execute(
            "UPDATE reading_exercises SET comprehension_status = 'generated', "
            "comprehension_questions = ?, comprehension_generated_at = ? WHERE id = ?",
            (
                _COMPREHENSION_SEP.join(questions),
                datetime.now(timezone.utc).isoformat(),
                exercise_id,
            ),
        )
        self._conn.commit()

    def mark_generation_failed(self, exercise_id: str) -> None:
        """Distinct from "pending" so the worker's next poll doesn't
        immediately retry (and likely fail identically on) the exact
        same content every cycle -- a parent's explicit "regenerate"
        (request_regeneration()) is what tries again."""
        self._conn.execute(
            "UPDATE reading_exercises SET comprehension_status = 'failed' WHERE id = ?",
            (exercise_id,),
        )
        self._conn.commit()

    def approve_questions(self, exercise_id: str, questions: list[str]) -> None:
        """The parent's own review step -- `questions` is whatever
        they ended up approving, which may be the worker's own text
        edited first. Only after this does Reading Partner ever speak
        these to the child (see _run_reading_partner())."""
        self._conn.execute(
            "UPDATE reading_exercises SET comprehension_status = 'approved', "
            "comprehension_questions = ?, comprehension_approved_at = ? WHERE id = ?",
            (
                _COMPREHENSION_SEP.join(questions),
                datetime.now(timezone.utc).isoformat(),
                exercise_id,
            ),
        )
        self._conn.commit()

    def request_regeneration(self, exercise_id: str) -> None:
        """Resets back to "pending" so comprehension_worker.py's next
        poll generates a fresh set -- used both for a "failed" item
        and for a parent who simply wants different questions than
        what's already been generated/approved."""
        self._conn.execute(
            "UPDATE reading_exercises SET comprehension_status = 'pending', "
            "comprehension_questions = '', comprehension_generated_at = NULL, "
            "comprehension_approved_at = NULL WHERE id = ?",
            (exercise_id,),
        )
        self._conn.commit()


def _row_to_exercise(row: sqlite3.Row) -> ReadingExerciseRecord:
    return ReadingExerciseRecord(
        id=row["id"],
        child_profile_id=row["child_profile_id"],
        title=row["title"],
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
        consumed_at=datetime.fromisoformat(row["consumed_at"]) if row["consumed_at"] else None,
        comprehension_status=row["comprehension_status"],
        comprehension_questions=[
            q for q in row["comprehension_questions"].split(_COMPREHENSION_SEP) if q
        ],
        comprehension_generated_at=(
            datetime.fromisoformat(row["comprehension_generated_at"])
            if row["comprehension_generated_at"]
            else None
        ),
        comprehension_approved_at=(
            datetime.fromisoformat(row["comprehension_approved_at"])
            if row["comprehension_approved_at"]
            else None
        ),
    )
