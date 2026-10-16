"""Unit tests for companion_robot.transcripts.repository.TranscriptRepository
-- backed by an in-memory SQLite database, no real audio/LLM needed.
"""
from datetime import datetime, timedelta, timezone

from companion_robot.engagement.schema import EngagementMode
from companion_robot.memory.schema import ConsentStatus
from companion_robot.storage.sqlite import connect
from companion_robot.transcripts.repository import TranscriptRepository
from companion_robot.transcripts.schema import TranscriptRecord


def _make_repo() -> TranscriptRepository:
    conn = connect(":memory:")
    return TranscriptRepository(conn)


def _make_record(
    record_id: str = "tr-1",
    child_profile_id: str = "anna",
    mode: EngagementMode = EngagementMode.EVERYDAY_COMPANION,
    content: str = "user: hi\nassistant: hello!",
    created_at=None,
    expires_at=None,
) -> TranscriptRecord:
    return TranscriptRecord(
        id=record_id,
        child_profile_id=child_profile_id,
        mode=mode,
        content=content,
        created_at=created_at or datetime.now(timezone.utc),
        consent_or_authorization_status=ConsentStatus.GRANTED,
        retention_policy="demo",
        expires_at=expires_at,
    )


def test_create_and_list_for_child_roundtrip():
    repo = _make_repo()
    repo.create(_make_record())

    records = repo.list_for_child("anna")

    assert len(records) == 1
    assert records[0].content == "user: hi\nassistant: hello!"
    assert records[0].mode == EngagementMode.EVERYDAY_COMPANION


def test_list_for_child_is_scoped_by_profile():
    repo = _make_repo()
    repo.create(_make_record(record_id="tr-1", child_profile_id="anna"))
    repo.create(_make_record(record_id="tr-2", child_profile_id="mika"))

    assert len(repo.list_for_child("anna")) == 1
    assert len(repo.list_for_child("mika")) == 1
    assert repo.list_for_child("someone-else") == []


def test_expired_record_is_excluded_like_memory_repository():
    """Same "expired behaves like already deleted" rule as
    memory/repository.py -- excluded from list_for_child() even
    before purge_expired() runs."""
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(_make_record(expires_at=now - timedelta(days=1)))

    assert repo.list_for_child("anna") == []


def test_purge_expired_only_removes_expired_rows():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(_make_record(record_id="expired", expires_at=now - timedelta(days=1)))
    repo.create(_make_record(record_id="fresh", expires_at=now + timedelta(days=90)))

    removed = repo.purge_expired()

    assert removed == 1
    remaining_ids = {r.id for r in repo.list_for_child("anna")}
    assert remaining_ids == {"fresh"}


def test_delete_removes_only_the_matching_profiles_record():
    repo = _make_repo()
    repo.create(_make_record(record_id="tr-1", child_profile_id="anna"))
    repo.create(_make_record(record_id="tr-2", child_profile_id="mika"))

    assert repo.delete("tr-1", "anna") is True
    assert repo.delete("tr-2", "anna") is False  # wrong profile, not deleted
    assert len(repo.list_for_child("anna")) == 0
    assert len(repo.list_for_child("mika")) == 1
