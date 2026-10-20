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


def test_feedback_surfaces_every_real_missed_word_not_just_the_hinted_one():
    """Decision 0060, found live: the hint-and-retry loop (decision
    0052) only ever addresses ONE word per book, so a session with two
    real misses left the second one completely unmentioned -- the
    final feedback either praised an unrelated word or said nothing
    actionable. Both real misses must now surface."""
    result = assess(
        "little bunny hops in the garden", "silly bunny hops in the gotten", duration_seconds=3.0
    )
    text = build_reading_feedback(result, MasteryDelta())

    assert '"little"' in text
    assert '"garden"' in text


def test_feedback_excludes_the_resolved_hint_word_but_keeps_other_misses():
    """The word the hint-and-retry loop (decision 0052) already fixed
    live is excluded -- re-mentioning it seconds later would feel
    redundant -- but a second, never-addressed miss still surfaces."""
    result = assess(
        "little bunny hops in the garden", "silly bunny hops in the gotten", duration_seconds=3.0
    )
    text = build_reading_feedback(result, MasteryDelta(), resolved_words=["little"])

    assert '"little"' not in text
    assert '"garden"' in text


def test_feedback_excludes_multiple_resolved_words_at_once():
    """Decision 0065: the hint ladder now works through every real
    miss, not just one -- resolved_words must accept (and exclude)
    more than a single word."""
    result = assess(
        "little bunny hops in the garden",
        "silly bunny hops in the dotten",
        duration_seconds=3.0,
    )
    text = build_reading_feedback(result, MasteryDelta(), resolved_words=["little", "garden"])

    assert '"little"' not in text
    assert '"garden"' not in text


def test_feedback_caps_practice_words_at_three():
    result = assess(
        "little garden purple yellow orange banana",
        "silly gotten people mellow orchid bandana",
        duration_seconds=3.0,
    )
    text = build_reading_feedback(result, MasteryDelta())

    mentioned = sum(
        f'"{w}"' in text for w in ("little", "garden", "purple", "yellow", "orange", "banana")
    )
    assert mentioned == 3
