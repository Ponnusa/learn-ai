"""Unit tests for companion_robot.reading.repository.ReadingRepository
-- real in-memory SQLite, no network/hardware."""
from companion_robot.reading.mastery import update_from_evidence
from companion_robot.reading.repository import ReadingRepository
from companion_robot.storage.sqlite import connect


def _repo() -> ReadingRepository:
    return ReadingRepository(connect(":memory:"))


def test_get_or_create_makes_a_fresh_profile_with_every_grapheme():
    repo = _repo()
    profile = repo.get_or_create("child-1", interest="dinosaurs")

    assert profile.interest == "dinosaurs"
    assert profile.sessions_completed == 0
    assert len(profile.masteries) > 0
    assert "a" in profile.masteries


def test_get_or_create_returns_the_same_profile_on_a_second_call():
    repo = _repo()
    repo.get_or_create("child-1", interest="dinosaurs")

    reloaded = repo.get_or_create("child-1", interest="ignored -- already exists")

    assert reloaded.interest == "dinosaurs"  # the original interest, not the second call's


def test_save_persists_mastery_updates_across_reloads():
    repo = _repo()
    profile = repo.get_or_create("child-1")
    update_from_evidence(profile, {"a": [True] * 10}, session_index=0)
    profile.sessions_completed = 1
    repo.save(profile)

    reloaded = repo.get_or_create("child-1")

    assert reloaded.sessions_completed == 1
    assert reloaded.masteries["a"].is_mastered()
    assert reloaded.masteries["a"].opportunities == 10


def test_profiles_are_scoped_per_child():
    repo = _repo()
    profile_a = repo.get_or_create("child-a")
    update_from_evidence(profile_a, {"a": [True] * 10}, session_index=0)
    repo.save(profile_a)

    profile_b = repo.get_or_create("child-b")

    assert not profile_b.masteries["a"].is_mastered()


def test_sight_words_round_trip():
    repo = _repo()
    profile = repo.get_or_create("child-1")
    profile.sight_words = ["the", "was"]
    repo.save(profile)

    reloaded = repo.get_or_create("child-1")

    assert reloaded.sight_words == ["the", "was"]


def test_new_profile_has_no_passage_in_progress():
    repo = _repo()
    profile = repo.get_or_create("child-1")

    assert profile.current_passage_key is None
    assert profile.current_sentence_index == 0


def test_passage_position_round_trip():
    """Decision 0067: a mid-passage position must survive a reload --
    the whole point is resuming across separate sessions/processes,
    not just within one in-memory run."""
    repo = _repo()
    profile = repo.get_or_create("child-1")
    profile.current_passage_key = "abc123"
    profile.current_sentence_index = 2
    repo.save(profile)

    reloaded = repo.get_or_create("child-1")

    assert reloaded.current_passage_key == "abc123"
    assert reloaded.current_sentence_index == 2


def test_passage_position_resets_to_none_round_trip():
    """A finished passage resets its position -- confirms None itself
    round-trips back to None, not the string "None" or some other
    truthy placeholder."""
    repo = _repo()
    profile = repo.get_or_create("child-1")
    profile.current_passage_key = "abc123"
    profile.current_sentence_index = 2
    repo.save(profile)

    profile.current_passage_key = None
    profile.current_sentence_index = 0
    repo.save(profile)
    reloaded = repo.get_or_create("child-1")

    assert reloaded.current_passage_key is None
    assert reloaded.current_sentence_index == 0
