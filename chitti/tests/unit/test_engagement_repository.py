"""Unit tests for companion_robot.engagement.repository.EngagementRepository
-- backed by an in-memory SQLite database, no real audio/LLM needed.
"""
from datetime import datetime, timedelta, timezone

from companion_robot.engagement.repository import EngagementRepository
from companion_robot.engagement.schema import EngagementMode, EngagementSession
from companion_robot.storage.sqlite import connect


def _make_repo() -> EngagementRepository:
    conn = connect(":memory:")
    return EngagementRepository(conn)


def _make_session(
    session_id: str = "eng-1",
    child_profile_id: str = "anna",
    mode: EngagementMode = EngagementMode.TEACHABLE_FRIEND,
    turn_count: int = 3,
    word_count: int = 20,
    created_at=None,
) -> EngagementSession:
    return EngagementSession(
        id=session_id,
        child_profile_id=child_profile_id,
        mode=mode,
        turn_count=turn_count,
        word_count=word_count,
        created_at=created_at or datetime.now(timezone.utc),
    )


def test_create_and_list_for_child_roundtrip():
    repo = _make_repo()
    repo.create(_make_session())

    sessions = repo.list_for_child("anna")

    assert len(sessions) == 1
    assert sessions[0].turn_count == 3
    assert sessions[0].word_count == 20
    assert sessions[0].mode == EngagementMode.TEACHABLE_FRIEND


def test_list_for_child_is_scoped_by_profile():
    repo = _make_repo()
    repo.create(_make_session(session_id="eng-1", child_profile_id="anna"))
    repo.create(_make_session(session_id="eng-2", child_profile_id="mika"))

    assert len(repo.list_for_child("anna")) == 1
    assert len(repo.list_for_child("mika")) == 1
    assert repo.list_for_child("someone-else") == []


def test_latest_for_child_picks_the_most_recent():
    repo = _make_repo()
    now = datetime.now(timezone.utc)
    repo.create(_make_session(session_id="old", created_at=now - timedelta(days=1)))
    repo.create(_make_session(session_id="new", created_at=now))

    latest = repo.latest_for_child("anna")

    assert latest.id == "new"


def test_latest_for_child_returns_none_when_no_sessions_exist():
    repo = _make_repo()

    assert repo.latest_for_child("anna") is None


def test_everyday_companion_mode_roundtrips():
    """Decision 0034: the third mode, same storage as the other two."""
    repo = _make_repo()
    repo.create(_make_session(mode=EngagementMode.EVERYDAY_COMPANION))

    sessions = repo.list_for_child("anna")

    assert sessions[0].mode == EngagementMode.EVERYDAY_COMPANION
