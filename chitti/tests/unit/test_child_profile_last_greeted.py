"""Unit tests for ChildProfile/ChildProfileRepository's
last_greeted_date field and mark_greeted() (decision 0108) -- lets
voice_loop_demo.py's welcome-back recap skip re-running its own LLM
call on every restart within the same day.
"""
from datetime import datetime, timezone

from companion_robot.parent_controls.profiles import ChildProfile, ChildProfileRepository
from companion_robot.storage.sqlite import connect


def _make_repo() -> ChildProfileRepository:
    return ChildProfileRepository(connect(":memory:"))


def test_default_last_greeted_date_is_empty():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(ChildProfile(id="p1", name="Anna", age=7, created_at=now, updated_at=now))

    assert repo.get("p1").last_greeted_date == ""


def test_mark_greeted_sets_the_date():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(ChildProfile(id="p1", name="Anna", age=7, created_at=now, updated_at=now))

    repo.mark_greeted("p1", "2026-10-24")

    assert repo.get("p1").last_greeted_date == "2026-10-24"


def test_mark_greeted_leaves_other_fields_unchanged():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(
        ChildProfile(id="p1", name="Anna", age=7, created_at=now, updated_at=now, interest="space")
    )

    repo.mark_greeted("p1", "2026-10-24")

    updated = repo.get("p1")
    assert updated.name == "Anna"
    assert updated.interest == "space"


def test_mark_greeted_is_a_noop_for_an_unknown_profile():
    """Must not raise -- same forgiving shape as delete()'s own
    rowcount check, just nothing to update here."""
    repo = _make_repo()
    repo.mark_greeted("does-not-exist", "2026-10-24")
