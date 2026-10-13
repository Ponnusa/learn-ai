"""Unit tests for companion_robot.reminders.repository.ReminderRepository
-- backed by an in-memory SQLite database, no real scheduler/hardware
needed.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from companion_robot.reminders.repository import ReminderRepository
from companion_robot.reminders.schema import Recurrence, ReminderRecord, ReminderSource
from companion_robot.storage.sqlite import connect

_HELSINKI = ZoneInfo("Europe/Helsinki")


def _make_repo() -> ReminderRepository:
    conn = connect(":memory:")
    return ReminderRepository(conn)


def _make_record(
    record_id: str = "rem-1",
    child_profile_id: str = "anna",
    text: str = "Brush your teeth",
    scheduled_at=None,
    recurrence: Recurrence | None = None,
    is_alarm: bool = False,
) -> ReminderRecord:
    now = datetime.now(timezone.utc)
    return ReminderRecord(
        id=record_id,
        child_profile_id=child_profile_id,
        text=text,
        scheduled_at=scheduled_at or now,
        source=ReminderSource.PARENT,
        created_at=now,
        updated_at=now,
        recurrence=recurrence,
        is_alarm=is_alarm,
    )


def test_create_and_get_round_trip():
    repo = _make_repo()
    repo.create(_make_record())

    fetched = repo.get("rem-1", "anna")
    assert fetched is not None
    assert fetched.text == "Brush your teeth"


def test_get_is_scoped_to_child_profile():
    repo = _make_repo()
    repo.create(_make_record(child_profile_id="anna"))

    assert repo.get("rem-1", "anna") is not None
    assert repo.get("rem-1", "timmy") is None


def test_list_for_child_excludes_other_profiles_and_filters_enabled():
    repo = _make_repo()
    repo.create(_make_record(record_id="rem-1", child_profile_id="anna"))
    repo.create(_make_record(record_id="rem-2", child_profile_id="timmy"))
    repo.set_enabled("rem-1", "anna", False)

    assert [r.id for r in repo.list_for_child("anna")] == ["rem-1"]
    assert repo.list_for_child("anna", enabled_only=True) == []


def test_update_text_rejects_wrong_profile():
    repo = _make_repo()
    repo.create(_make_record())

    assert repo.update_text("rem-1", "timmy", "hijacked") is False
    assert repo.update_text("rem-1", "anna", "Feed the fish") is True
    assert repo.get("rem-1", "anna").text == "Feed the fish"


def test_delete_rejects_wrong_profile():
    repo = _make_repo()
    repo.create(_make_record())

    assert repo.delete("rem-1", "timmy") is False
    assert repo.delete("rem-1", "anna") is True
    assert repo.get("rem-1", "anna") is None


def test_due_reminders_only_returns_enabled_and_past_due():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(_make_record(record_id="past-due", scheduled_at=now - timedelta(minutes=5)))
    repo.create(_make_record(record_id="future", scheduled_at=now + timedelta(hours=1)))
    repo.create(_make_record(record_id="disabled-past-due", scheduled_at=now - timedelta(minutes=5)))
    repo.set_enabled("disabled-past-due", "anna", False)

    due = repo.due_reminders(now)

    assert [r.id for r in due] == ["past-due"]


def test_mark_fired_disables_one_time_reminder():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(_make_record(scheduled_at=now - timedelta(minutes=1)))

    updated = repo.mark_fired("rem-1", "anna", now)

    assert updated.enabled is False
    assert repo.due_reminders(now) == []


def test_mark_fired_advances_recurring_reminder_and_keeps_it_enabled():
    repo = _make_repo()
    scheduled = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
    repo.create(_make_record(scheduled_at=scheduled, recurrence=Recurrence.DAILY))

    updated = repo.mark_fired("rem-1", "anna", scheduled)

    assert updated.enabled is True
    assert updated.scheduled_at == datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)


def test_mark_fired_recurring_reminder_handles_dst_transition_correctly():
    """Spec section 8 explicitly requires handling daylight-saving
    changes. A daily 8am reminder in Europe/Helsinki should still fire
    at 8am local time the day after a DST transition, not 24 real
    hours later at a shifted wall-clock time."""
    repo = _make_repo()
    before_dst = datetime(2026, 3, 28, 8, 0, tzinfo=_HELSINKI)
    repo.create(
        _make_record(scheduled_at=before_dst, recurrence=Recurrence.DAILY)
    )

    updated = repo.mark_fired("rem-1", "anna", before_dst)

    after_dst = datetime(2026, 3, 29, 8, 0, tzinfo=_HELSINKI)
    assert updated.scheduled_at == after_dst
    # UTC offset shifted from +2 to +3 across the transition, but the
    # local wall-clock hour (8am) is preserved either way.
    assert before_dst.utcoffset() != after_dst.utcoffset()
    assert updated.scheduled_at.hour == 8


def test_alarm_flag_round_trips():
    repo = _make_repo()
    repo.create(_make_record(is_alarm=True))

    assert repo.get("rem-1", "anna").is_alarm is True
