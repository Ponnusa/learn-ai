"""Unit tests for companion_robot.education.math_check.extract_addition_claim
-- pure function, no I/O, no real LLM needed.
"""
from companion_robot.education.math_check import extract_addition_claim


def test_extracts_a_correct_claim_in_digits():
    result = extract_addition_claim("2+2=4")

    assert result.a == 2
    assert result.b == 2
    assert result.claimed_sum == 4
    assert result.correct_sum == 4
    assert result.correct is True


def test_extracts_a_correct_claim_in_words():
    result = extract_addition_claim("One plus one is two")

    assert result.a == 1
    assert result.b == 1
    assert result.claimed_sum == 2
    assert result.correct is True


def test_extracts_an_incorrect_claim():
    result = extract_addition_claim("two plus two is three")

    assert result.a == 2
    assert result.b == 2
    assert result.claimed_sum == 3
    assert result.correct_sum == 4
    assert result.correct is False


def test_accepts_equals_and_makes_as_well_as_is():
    assert extract_addition_claim("4 plus 2 equals 6").correct is True
    assert extract_addition_claim("4 plus 2 makes 6").correct is True


def test_is_case_insensitive():
    result = extract_addition_claim("FOUR PLUS TWO IS SIX")

    assert result.correct is True


def test_returns_none_for_ordinary_conversation():
    assert extract_addition_claim("Dogs can smell really well") is None


def test_returns_none_for_multi_word_numbers():
    """Documented gap, not a silent wrong guess -- "twenty two" isn't
    in the word-number map, so this returns None rather than
    mis-parsing it as something else."""
    assert extract_addition_claim("twenty two plus one is twenty three") is None


def test_returns_none_when_a_token_in_the_pattern_is_not_a_number():
    assert extract_addition_claim("my friend plus my dog is happy") is None
