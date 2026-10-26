"""Unit tests for companion_robot.reading.hints -- deterministic,
no-LLM selection of which missed word(s) in a sentence need
attention (decision 0052). The graduated hint-ladder TEXT this module
used to build (build_hint_line()/HINT_STAGES) is gone as of decision
0116 -- voice_loop_demo.py's own correction flow no longer teaches
phonics or plays any sound clip; it just re-speaks the missed word
slow/medium/fast and checks the child's attempt."""
from companion_robot.reading.alignment import assess
from companion_robot.reading.hints import pick_hint_word, pick_hint_words


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


def test_pick_hint_word_skips_a_trivially_short_word():
    """Found live: "a" got selected as a hint target -- "that word
    starts with the 'a' sound" is nonsensical for a word that IS the
    sound. The search should continue past it to the next real,
    substantial miscue instead of hinting on it."""
    result = assess("a cat sat", "I cat mat", duration_seconds=3.0)
    assert pick_hint_word(result) == "sat"  # not "a"


def test_pick_hint_word_returns_none_when_every_miscue_is_too_short():
    result = assess("a is it", "I are at", duration_seconds=3.0)
    assert pick_hint_word(result) is None


def test_pick_hint_word_skips_a_sight_word():
    """Decision 0058, also found live: "the" passed the length check
    but is a sight word (meant to be recognized by memory, not sounded
    out) -- the search should continue to the next real, decodable
    miscue instead of hinting on it."""
    result = assess("the cat sat", "a cat mat", duration_seconds=3.0)
    assert pick_hint_word(result) == "sat"  # not "the"


def test_pick_hint_word_returns_none_when_every_miscue_is_a_sight_word():
    result = assess("the was said", "a is told", duration_seconds=3.0)
    assert pick_hint_word(result) is None


def test_every_inventory_grapheme_has_a_sound_example():
    """Decision 0064: the lookup must cover every grapheme
    decodability.decompose() can actually return -- a missing entry
    would silently fall back to the bare letter, the exact bug this
    table exists to avoid."""
    from companion_robot.reading.curriculum import GRAPHEME_INVENTORY
    from companion_robot.reading.hints import _SOUND_EXAMPLES

    real_graphemes = [
        g for g, _level in GRAPHEME_INVENTORY if not g.startswith("-") and g != "_blend_"
    ]
    assert all(g in _SOUND_EXAMPLES for g in real_graphemes)


# -- pick_hint_words() (decision 0065) -------------------------------------


def test_pick_hint_words_returns_every_real_miss_in_order():
    result = assess("cat sat mat rug", "cat sit mat bug", duration_seconds=3.0)
    assert pick_hint_words(result) == ["sat", "rug"]


def test_pick_hint_words_caps_at_max_words():
    result = assess(
        "cat sat mat rug dog pit", "cot sit mit rag dig pot", duration_seconds=3.0
    )
    words = pick_hint_words(result, max_words=2)
    assert len(words) == 2


def test_pick_hint_words_dedupes_the_same_word():
    result = assess("cat sat cat sat", "cot sit cot sit", duration_seconds=3.0)
    assert pick_hint_words(result) == ["cat", "sat"]


def test_pick_hint_words_returns_empty_list_on_a_clean_read():
    result = assess("cat sat mat", "cat sat mat", duration_seconds=3.0)
    assert pick_hint_words(result) == []


def test_pick_hint_word_is_the_first_of_pick_hint_words():
    result = assess("cat sat mat rug", "cat sit mat bug", duration_seconds=3.0)
    assert pick_hint_word(result) == pick_hint_words(result)[0]
