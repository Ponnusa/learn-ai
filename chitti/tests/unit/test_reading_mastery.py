"""Unit tests for companion_robot.reading.mastery -- the BKT update."""
from companion_robot.reading.mastery import update_from_evidence
from companion_robot.reading.schema import ReadingProfile


def test_correct_evidence_raises_mastery():
    profile = ReadingProfile.new("child-1")
    p_before = profile.masteries["a"].p_mastery

    delta = update_from_evidence(profile, {"a": [True, True, True]}, session_index=0)

    assert profile.masteries["a"].p_mastery > p_before
    assert delta.changes[0].grapheme == "a"
    assert delta.changes[0].n_correct == 3
    assert delta.changes[0].n_incorrect == 0


def test_incorrect_evidence_does_not_raise_mastery_as_much_as_correct():
    profile_correct = ReadingProfile.new("child-1")
    profile_incorrect = ReadingProfile.new("child-1")

    update_from_evidence(profile_correct, {"a": [True, True, True]}, session_index=0)
    update_from_evidence(profile_incorrect, {"a": [False, False, False]}, session_index=0)

    assert profile_correct.masteries["a"].p_mastery > profile_incorrect.masteries["a"].p_mastery


def test_newly_mastered_reported_when_crossing_threshold():
    profile = ReadingProfile.new("child-1")
    # Enough consecutive correct reads to cross MASTERY_THRESHOLD (0.95).
    delta = update_from_evidence(profile, {"a": [True] * 10}, session_index=0)

    assert "a" in delta.newly_mastered
    assert profile.masteries["a"].is_mastered()


def test_not_newly_mastered_when_already_mastered_before():
    profile = ReadingProfile.new("child-1")
    update_from_evidence(profile, {"a": [True] * 10}, session_index=0)

    delta = update_from_evidence(profile, {"a": [True]}, session_index=1)

    assert "a" not in delta.newly_mastered  # already crossed the threshold last time


def test_opportunities_and_correct_counts_accumulate():
    profile = ReadingProfile.new("child-1")
    update_from_evidence(profile, {"a": [True, False]}, session_index=0)
    update_from_evidence(profile, {"a": [True]}, session_index=1)

    mastery = profile.masteries["a"]
    assert mastery.opportunities == 3
    assert mastery.correct == 2


def test_last_seen_session_is_stamped():
    profile = ReadingProfile.new("child-1")
    update_from_evidence(profile, {"a": [True]}, session_index=5)

    assert profile.masteries["a"].last_seen_session == 5


def test_empty_evidence_list_is_skipped():
    profile = ReadingProfile.new("child-1")
    p_before = profile.masteries["a"].p_mastery

    delta = update_from_evidence(profile, {"a": []}, session_index=0)

    assert profile.masteries["a"].p_mastery == p_before
    assert delta.changes == []


def test_unknown_grapheme_is_created_on_demand():
    profile = ReadingProfile.new("child-1")
    del profile.masteries["sh"]  # simulate a grapheme missing from the profile

    update_from_evidence(profile, {"sh": [True]}, session_index=0)

    assert "sh" in profile.masteries
    assert profile.masteries["sh"].level == "digraphs"
