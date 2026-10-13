"""Unit tests for ChildProfile/ChildProfileRepository's speech_speed
field -- the parent-controlled TTS pace setting (decision 0016).
"""
from datetime import datetime, timezone

from companion_robot.parent_controls.profiles import ChildProfile, ChildProfileRepository
from companion_robot.storage.sqlite import connect


def _make_repo() -> ChildProfileRepository:
    return ChildProfileRepository(connect(":memory:"))


def test_default_speech_speed_is_normal_pace():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(ChildProfile(id="p1", name="Anna", age=7, created_at=now, updated_at=now))

    assert repo.get("p1").speech_speed == 1.0


def test_create_with_custom_speech_speed_round_trips():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(
        ChildProfile(
            id="p1", name="Anna", age=7, created_at=now, updated_at=now, speech_speed=0.8
        )
    )

    assert repo.get("p1").speech_speed == 0.8


def test_update_changes_speech_speed_and_leaves_other_fields():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(ChildProfile(id="p1", name="Anna", age=7, created_at=now, updated_at=now))

    assert repo.update("p1", speech_speed=0.85) is True

    updated = repo.get("p1")
    assert updated.speech_speed == 0.85
    assert updated.name == "Anna"
    assert updated.age == 7
