"""Unit tests for ChildProfile/ChildProfileRepository's interest field
-- the parent-controlled Reading Partner story theme (decision 0051
follow-up).
"""
from datetime import datetime, timezone

from companion_robot.parent_controls.profiles import ChildProfile, ChildProfileRepository
from companion_robot.storage.sqlite import connect


def _make_repo() -> ChildProfileRepository:
    return ChildProfileRepository(connect(":memory:"))


def test_default_interest_is_empty():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(ChildProfile(id="p1", name="Anna", age=7, created_at=now, updated_at=now))

    assert repo.get("p1").interest == ""


def test_create_with_custom_interest_round_trips():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(
        ChildProfile(
            id="p1", name="Anna", age=7, created_at=now, updated_at=now, interest="dinosaurs"
        )
    )

    assert repo.get("p1").interest == "dinosaurs"


def test_update_changes_interest_and_leaves_other_fields():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(ChildProfile(id="p1", name="Anna", age=7, created_at=now, updated_at=now))

    assert repo.update("p1", interest="space") is True

    updated = repo.get("p1")
    assert updated.interest == "space"
    assert updated.name == "Anna"
    assert updated.age == 7
