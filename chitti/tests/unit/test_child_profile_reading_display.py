"""Unit tests for ChildProfile/ChildProfileRepository's reading-display
fields -- the parent-controlled teleprompter pace/font size/font color
(decision 0053).
"""
from datetime import datetime, timezone

from companion_robot.parent_controls.profiles import ChildProfile, ChildProfileRepository
from companion_robot.storage.sqlite import connect


def _make_repo() -> ChildProfileRepository:
    return ChildProfileRepository(connect(":memory:"))


def test_defaults_match_todays_hardcoded_display():
    """Matches the values device/screen_face.py already hardcodes
    today, so a profile that never touches these settings renders
    exactly as before."""
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(ChildProfile(id="p1", name="Anna", age=7, created_at=now, updated_at=now))

    profile = repo.get("p1")
    assert profile.reading_pace_wpm == 45.0
    assert profile.reading_font_size == 28
    assert profile.reading_font_color == "white"


def test_create_with_custom_reading_display_settings_round_trips():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(
        ChildProfile(
            id="p1",
            name="Anna",
            age=7,
            created_at=now,
            updated_at=now,
            reading_pace_wpm=30.0,
            reading_font_size=36,
            reading_font_color="yellow",
        )
    )

    profile = repo.get("p1")
    assert profile.reading_pace_wpm == 30.0
    assert profile.reading_font_size == 36
    assert profile.reading_font_color == "yellow"


def test_update_changes_reading_display_settings_and_leaves_other_fields():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(ChildProfile(id="p1", name="Anna", age=7, created_at=now, updated_at=now))

    assert repo.update(
        "p1", reading_pace_wpm=60.0, reading_font_size=22, reading_font_color="cyan"
    ) is True

    updated = repo.get("p1")
    assert updated.reading_pace_wpm == 60.0
    assert updated.reading_font_size == 22
    assert updated.reading_font_color == "cyan"
    assert updated.name == "Anna"
    assert updated.age == 7
