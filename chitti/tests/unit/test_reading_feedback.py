"""Unit tests for companion_robot.reading.feedback -- the deterministic
spoken feedback, no LLM call."""
from companion_robot.reading.alignment import assess
from companion_robot.reading.feedback import build_reading_feedback
from companion_robot.reading.mastery import update_from_evidence
from companion_robot.reading.schema import MasteryDelta, ReadingProfile


def test_feedback_is_warm_for_a_perfect_read():
    result = assess("cat sat mat", "cat sat mat", duration_seconds=3.0)
    text = build_reading_feedback(result, MasteryDelta())
    assert "really well" in text


def test_feedback_never_mentions_raw_numbers():
    """Never raw accuracy/WCPM numbers dumped on a child -- qualitative
    framing only."""
    profile = ReadingProfile.new("child-1")
    result = assess("cat sat mat", "cat sit mat", duration_seconds=3.0)
    delta = update_from_evidence(profile, result.grapheme_evidence, session_index=0)

    text = build_reading_feedback(result, delta)

    assert str(result.accuracy) not in text
    assert str(result.wcpm) not in text
    assert "%" not in text


def test_feedback_mentions_newly_mastered_sounds():
    profile = ReadingProfile.new("child-1")
    result = assess("a", "a", duration_seconds=1.0)
    # Force 'a' past the mastery threshold with a batch of correct evidence.
    delta = update_from_evidence(profile, {"a": [True] * 10}, session_index=0)

    text = build_reading_feedback(result, delta)

    assert "'a'" in text


def test_feedback_encourages_on_a_rough_read_without_being_harsh():
    result = assess("cat sat mat", "dog dog dog", duration_seconds=3.0)
    text = build_reading_feedback(result, MasteryDelta())
    assert "tricky" in text.lower() or "good try" in text.lower()
