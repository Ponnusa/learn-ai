"""Unit tests for companion_robot.reading.hints -- the deterministic,
no-LLM graduated hint ladder (decision 0052)."""
from companion_robot.reading.alignment import assess
from companion_robot.reading.decodability import decompose
from companion_robot.reading.hints import build_hint_line, pick_hint_word


def test_pick_hint_word_returns_none_on_a_clean_read():
    result = assess("cat sat mat", "cat sat mat", duration_seconds=3.0)
    assert pick_hint_word(result) is None


def test_pick_hint_word_returns_none_when_only_self_corrected_or_hesitated():
    """self_correction/hesitation aren't real errors -- assess() itself
    doesn't count them against the child, and neither should hint
    selection."""
    result = assess("cat", "cot cat", duration_seconds=1.0)  # self-correction
    assert pick_hint_word(result) is None

    result = assess("cat sat", "cat cat sat", duration_seconds=1.0)  # hesitation
    assert pick_hint_word(result) is None


def test_pick_hint_word_picks_the_substituted_word():
    result = assess("cat sat mat", "cat sit mat", duration_seconds=3.0)
    assert pick_hint_word(result) == "sat"


def test_pick_hint_word_picks_the_omitted_word():
    result = assess("cat sat mat", "cat mat", duration_seconds=3.0)
    assert pick_hint_word(result) == "sat"


def test_pick_hint_word_picks_the_first_real_miscue_in_order():
    result = assess("cat sat mat rug", "cat sit mat bug", duration_seconds=3.0)
    assert pick_hint_word(result) == "sat"  # not "rug", which comes later


def test_build_hint_line_stage_0_is_encouragement():
    line = build_hint_line("sat", 0)
    assert "take your time" in line.lower()
    assert "sat" not in line  # not given away yet


def test_build_hint_line_stage_1_gives_the_first_sound():
    line = build_hint_line("sat", 1)
    first_sound = decompose("sat").graphemes[0].grapheme
    assert first_sound in line
    assert "sat" not in line  # still not the whole word


def test_build_hint_line_stage_2_says_the_word():
    line = build_hint_line("sat", 2)
    assert "sat" in line
