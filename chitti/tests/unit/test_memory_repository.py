"""Unit tests for companion_robot.memory.repository.MemoryRepository --
backed by an in-memory SQLite database, no real file/hardware needed.
"""
from datetime import datetime, timedelta, timezone

import pytest

from companion_robot.memory.repository import MemoryRepository
from companion_robot.memory.schema import (
    ConsentStatus,
    MemoryCategory,
    MemoryRecord,
    MemorySource,
)
from companion_robot.storage.sqlite import connect


def _make_repo() -> MemoryRepository:
    conn = connect(":memory:")
    return MemoryRepository(conn)


def _make_record(
    record_id: str = "rec-1",
    child_profile_id: str = "anna",
    category: MemoryCategory = MemoryCategory.PERSONAL_PREFERENCE,
    content: str = "likes dinosaurs",
    expires_at=None,
) -> MemoryRecord:
    now = datetime.now(timezone.utc)
    return MemoryRecord(
        id=record_id,
        child_profile_id=child_profile_id,
        category=category,
        content=content,
        created_at=now,
        updated_at=now,
        source=MemorySource.CHILD,
        consent_or_authorization_status=ConsentStatus.GRANTED,
        retention_policy="default",
        expires_at=expires_at,
    )


def test_create_and_get_round_trip():
    repo = _make_repo()
    repo.create(_make_record())

    fetched = repo.get("rec-1", "anna")
    assert fetched is not None
    assert fetched.content == "likes dinosaurs"
    assert fetched.child_profile_id == "anna"


def test_create_refuses_conversation_context():
    repo = _make_repo()
    record = _make_record(category=MemoryCategory.CONVERSATION_CONTEXT)
    with pytest.raises(ValueError, match="conversation_context"):
        repo.create(record)


def test_get_is_scoped_to_child_profile():
    repo = _make_repo()
    repo.create(_make_record(child_profile_id="anna"))

    assert repo.get("rec-1", "anna") is not None
    assert repo.get("rec-1", "timmy") is None


def test_list_for_child_excludes_other_profiles():
    repo = _make_repo()
    repo.create(_make_record(record_id="rec-1", child_profile_id="anna"))
    repo.create(_make_record(record_id="rec-2", child_profile_id="timmy"))

    anna_records = repo.list_for_child("anna")
    assert [r.id for r in anna_records] == ["rec-1"]


def test_list_for_child_filters_by_category():
    repo = _make_repo()
    repo.create(_make_record(record_id="rec-1", category=MemoryCategory.PERSONAL_PREFERENCE))
    repo.create(_make_record(record_id="rec-2", category=MemoryCategory.LEARNING_STATE))

    prefs = repo.list_for_child("anna", category=MemoryCategory.PERSONAL_PREFERENCE)
    assert [r.id for r in prefs] == ["rec-1"]


def test_update_content_changes_content_and_rejects_wrong_profile():
    repo = _make_repo()
    repo.create(_make_record())

    assert repo.update_content("rec-1", "anna", "likes sharks now") is True
    assert repo.get("rec-1", "anna").content == "likes sharks now"
    assert repo.update_content("rec-1", "timmy", "hijacked") is False


def test_update_consent_changes_status():
    repo = _make_repo()
    repo.create(_make_record())

    assert repo.update_consent("rec-1", "anna", ConsentStatus.REVOKED) is True
    assert repo.get("rec-1", "anna").consent_or_authorization_status == ConsentStatus.REVOKED


def test_delete_removes_record_and_rejects_wrong_profile():
    repo = _make_repo()
    repo.create(_make_record())

    assert repo.delete("rec-1", "timmy") is False
    assert repo.get("rec-1", "anna") is not None
    assert repo.delete("rec-1", "anna") is True
    assert repo.get("rec-1", "anna") is None


def test_expired_record_excluded_from_get_and_list_without_explicit_purge():
    repo = _make_repo()
    past = datetime.now(timezone.utc) - timedelta(days=1)
    repo.create(_make_record(expires_at=past))

    assert repo.get("rec-1", "anna") is None
    assert repo.list_for_child("anna") == []


def test_purge_expired_removes_only_expired_rows():
    repo = _make_repo()
    past = datetime.now(timezone.utc) - timedelta(days=1)
    future = datetime.now(timezone.utc) + timedelta(days=30)
    repo.create(_make_record(record_id="expired", expires_at=past))
    repo.create(_make_record(record_id="still-valid", expires_at=future))
    repo.create(_make_record(record_id="never-expires", expires_at=None))

    removed = repo.purge_expired()

    assert removed == 1
    assert repo.get("still-valid", "anna") is not None
    assert repo.get("never-expires", "anna") is not None
