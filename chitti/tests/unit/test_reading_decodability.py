"""Unit tests for companion_robot.reading.decodability -- pure
functions, no dependencies.
"""
from companion_robot.reading.decodability import (
    check_decodability,
    clean_word,
    decompose,
    inflectional_suffix,
    is_word_decodable,
)


def test_decompose_simple_cvc_word():
    d = decompose("cat", mastered_levels=["short_vowels"])
    assert d.grapheme_strings == ["c", "a", "t"]
    assert d.is_decodable is True


def test_decompose_digraph_requires_digraphs_level():
    d = decompose("ship", mastered_levels=["short_vowels"])
    assert "sh" in d.grapheme_strings
    assert d.is_decodable is False  # digraphs not mastered yet
    assert decompose("ship", mastered_levels=["short_vowels", "digraphs"]).is_decodable is True


def test_decompose_silent_e():
    d = decompose("make", mastered_levels=["short_vowels", "silent_e"])
    assert "a_e" in d.grapheme_strings
    assert d.is_decodable is True
    assert decompose("make", mastered_levels=["short_vowels"]).is_decodable is False


def test_decompose_blend_requires_blends_level():
    """Two adjacent consonant units need the 'blends' level, even
    though each individual consonant is already a mastered short_vowels
    grapheme on its own."""
    assert decompose("stop", mastered_levels=["short_vowels"]).is_decodable is False
    assert decompose("stop", mastered_levels=["short_vowels", "blends"]).is_decodable is True


def test_decompose_r_controlled():
    d = decompose("car", mastered_levels=["short_vowels", "r_controlled"])
    assert "ar" in d.grapheme_strings
    assert d.is_decodable is True


def test_decompose_glued_sound():
    d = decompose("sing", mastered_levels=["short_vowels", "glued_sounds"])
    assert "ing" in d.grapheme_strings
    assert d.is_decodable is True


def test_decompose_sight_word_always_decodable():
    d = decompose("the", mastered_levels=[], sight_words={"the"})
    assert d.is_decodable is True
    assert d.is_sight_word is True


def test_decompose_suffix_on_decodable_base():
    """'jumps' is not itself in the base inventory (double consonant +
    plain 's'), but once 'suffixes' is mastered, stripping the -s and
    checking the base word is enough."""
    assert is_word_decodable("cats", ["short_vowels", "suffixes"]) is True
    assert is_word_decodable("cats", ["short_vowels"]) is False


def test_inflectional_suffix_detection():
    assert inflectional_suffix("jumping") == "ing"
    assert inflectional_suffix("jumped") == "ed"
    assert inflectional_suffix("foxes") == "es"
    assert inflectional_suffix("cats") == "s"
    assert inflectional_suffix("cat") is None
    assert inflectional_suffix("class") is None  # ends in -ss, not a suffix


def test_clean_word_strips_punctuation_and_lowercases():
    assert clean_word("Cat!") == "cat"
    assert clean_word("don’t") == "don't"


def test_check_decodability_all_words_ok():
    check = check_decodability("cat sat mat", {"mastered_levels": ["short_vowels"]})
    assert check["is_decodable"] is True
    assert check["violations"] == []


def test_check_decodability_reports_violations_deduplicated():
    check = check_decodability(
        "cat ship ship", {"mastered_levels": ["short_vowels"], "target_level": None}
    )
    assert check["is_decodable"] is False
    assert check["violations"] == ["ship"]  # only once, despite appearing twice


def test_check_decodability_sight_words_always_allowed():
    check = check_decodability(
        "the cat sat", {"mastered_levels": ["short_vowels"], "sight_words": []}
    )
    assert check["is_decodable"] is True  # "the" is a DEFAULT_SIGHT_WORDS entry
