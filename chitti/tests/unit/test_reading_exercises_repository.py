"""Unit tests for companion_robot.parent_controls.reading_exercises --
real in-memory SQLite, no network/hardware (decision 0052)."""
from datetime import datetime, timezone

from companion_robot.parent_controls.reading_exercises import (
    ReadingExerciseRecord,
    ReadingExerciseRepository,
)
from companion_robot.storage.sqlite import connect


def _repo() -> ReadingExerciseRepository:
    return ReadingExerciseRepository(connect(":memory:"))


def _exercise(id_: str, child_profile_id: str = "child-1", **overrides) -> ReadingExerciseRecord:
    defaults = dict(
        id=id_,
        child_profile_id=child_profile_id,
        title="Homework",
        content="The cat sat.",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return ReadingExerciseRecord(**defaults)


def test_next_pending_for_child_returns_none_when_there_are_none():
    repo = _repo()
    assert repo.next_pending_for_child("child-1") is None


def test_next_pending_for_child_returns_the_oldest_unconsumed_one():
    repo = _repo()
    repo.create(_exercise("e1", title="First", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    repo.create(_exercise("e2", title="Second", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)))

    pending = repo.next_pending_for_child("child-1")

    assert pending is not None
    assert pending.title == "First"


def test_mark_consumed_removes_it_from_pending():
    repo = _repo()
    repo.create(_exercise("e1", title="First", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    repo.create(_exercise("e2", title="Second", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)))

    repo.mark_consumed("e1")

    pending = repo.next_pending_for_child("child-1")
    assert pending is not None
    assert pending.title == "Second"


def test_list_for_child_includes_consumed_and_pending():
    repo = _repo()
    repo.create(_exercise("e1"))
    repo.mark_consumed("e1")
    repo.create(_exercise("e2"))

    records = repo.list_for_child("child-1")

    assert {r.id for r in records} == {"e1", "e2"}
    consumed = next(r for r in records if r.id == "e1")
    assert consumed.consumed_at is not None
    pending = next(r for r in records if r.id == "e2")
    assert pending.consumed_at is None


def test_exercises_are_scoped_per_child():
    repo = _repo()
    repo.create(_exercise("e1", child_profile_id="child-a"))

    assert repo.next_pending_for_child("child-b") is None
    assert repo.list_for_child("child-b") == []


def test_delete_removes_the_exercise():
    repo = _repo()
    repo.create(_exercise("e1"))

    assert repo.delete("e1") is True
    assert repo.list_for_child("child-1") == []
    assert repo.delete("e1") is False


# -- Decision 0131: comprehension-question generation/approval ------------


def test_new_exercise_starts_pending_with_no_questions():
    repo = _repo()
    repo.create(_exercise("e1"))

    exercise = repo.list_for_child("child-1")[0]
    assert exercise.comprehension_status == "pending"
    assert exercise.comprehension_questions == []


def test_list_awaiting_generation_only_returns_pending_ones_across_children():
    repo = _repo()
    repo.create(_exercise("e1", child_profile_id="child-a"))
    repo.create(_exercise("e2", child_profile_id="child-b"))
    repo.save_generated_questions("e2", ["Q?"])

    awaiting = repo.list_awaiting_generation()

    assert [e.id for e in awaiting] == ["e1"]


def test_save_generated_questions_moves_to_generated_not_approved():
    repo = _repo()
    repo.create(_exercise("e1"))

    repo.save_generated_questions("e1", ["Where did the cat sit?", "What color was the cat?"])

    exercise = repo.list_for_child("child-1")[0]
    assert exercise.comprehension_status == "generated"
    assert exercise.comprehension_questions == [
        "Where did the cat sit?", "What color was the cat?",
    ]
    assert exercise.comprehension_generated_at is not None
    assert exercise.comprehension_approved_at is None


def test_mark_generation_failed_is_not_picked_up_again_by_list_awaiting_generation():
    """Decision 0131: distinct from "pending" so the worker's next
    poll doesn't immediately retry the exact same content every
    cycle."""
    repo = _repo()
    repo.create(_exercise("e1"))

    repo.mark_generation_failed("e1")

    assert repo.list_awaiting_generation() == []
    assert repo.list_for_child("child-1")[0].comprehension_status == "failed"


def test_approve_questions_lets_a_parent_edit_before_approving():
    repo = _repo()
    repo.create(_exercise("e1"))
    repo.save_generated_questions("e1", ["Where did the cat sit?"])

    repo.approve_questions("e1", ["Where did the cat sit?", "A parent-added question?"])

    exercise = repo.list_for_child("child-1")[0]
    assert exercise.comprehension_status == "approved"
    assert exercise.comprehension_questions == [
        "Where did the cat sit?", "A parent-added question?",
    ]
    assert exercise.comprehension_approved_at is not None


def test_request_regeneration_resets_an_approved_exercise_back_to_pending():
    repo = _repo()
    repo.create(_exercise("e1"))
    repo.approve_questions("e1", ["Where did the cat sit?"])

    repo.request_regeneration("e1")

    exercise = repo.list_for_child("child-1")[0]
    assert exercise.comprehension_status == "pending"
    assert exercise.comprehension_questions == []
    assert exercise.comprehension_generated_at is None
    assert exercise.comprehension_approved_at is None
    assert [e.id for e in repo.list_awaiting_generation()] == ["e1"]
