"""Unit tests for companion_robot.reading.feedback -- the deterministic
spoken feedback, no LLM call (decision 0055's evidence-based redesign,
replacing decision 0051's original mastery-sound announcement)."""
from companion_robot.reading.alignment import assess
from companion_robot.reading.feedback import build_reading_feedback
from companion_robot.reading.schema import MasteryDelta


def test_feedback_is_warm_for_a_perfect_read():
    result = assess("cat sat mat", "cat sat mat", duration_seconds=3.0)
    text = build_reading_feedback(result, MasteryDelta())
    assert "really well" in text


def test_feedback_never_mentions_raw_numbers():
    """Never raw accuracy/WCPM numbers dumped on a child -- qualitative
    framing only."""
    result = assess("cat sat mat", "cat sit mat", duration_seconds=3.0)
    text = build_reading_feedback(result, MasteryDelta())

    assert str(result.accuracy) not in text
    assert str(result.wcpm) not in text
    assert "%" not in text


def test_feedback_encourages_on_a_rough_read_without_being_harsh():
    result = assess("cat sat mat", "dog dog dog", duration_seconds=3.0)
    text = build_reading_feedback(result, MasteryDelta())
    assert "tricky" in text.lower() or "good try" in text.lower()


def test_feedback_cites_a_specific_standout_word_on_a_clean_read():
    """Decision 0055: evidence from the actual read (a real word the
    child said correctly) instead of a list of phonics sound labels
    (found live: an 18-item list in one breath read as overwhelming
    and disconnected from the reading itself)."""
    result = assess("a little bunny hops", "a little bunny hops", duration_seconds=3.0)
    text = build_reading_feedback(result, MasteryDelta())

    assert '"little"' in text  # the longest correctly-read word


def test_feedback_skips_the_standout_sentence_with_no_notable_word():
    """Every correctly-read word is too short to be a notable callout
    -- no forced/awkward praise."""
    result = assess("a is it", "a is it", duration_seconds=3.0)
    text = build_reading_feedback(result, MasteryDelta())

    assert text == "Wow, you read that really well!"


def test_feedback_mentions_the_unresolved_hint_word_instead_of_a_standout():
    """When the hint-and-retry loop (decision 0052) never got a
    correct retry, the final feedback gently points back at that one
    word rather than praising an unrelated standout."""
    result = assess("a little bunny hops", "a little bunny hops", duration_seconds=3.0)
    text = build_reading_feedback(result, MasteryDelta(), hint_word="hops")

    assert '"hops"' in text
    assert '"bunny"' not in text


def test_feedback_omits_the_hint_word_once_it_was_resolved():
    """The caller passes hint_word=None once the child got it right --
    covered by the default, documenting the contract here."""
    result = assess("a little bunny hops", "a little bunny hops", duration_seconds=3.0)
    text = build_reading_feedback(result, MasteryDelta(), hint_word=None)

    assert "Let's keep practicing" not in text
