"""Unit tests for companion_robot.education.math_check -- pure
functions, no I/O, no real LLM needed.
"""
from companion_robot.education.math_check import (
    extract_addition_claim,
    extract_bare_number,
    extract_posed_challenge,
)


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


def test_extract_posed_challenge_recognizes_the_plus_shape():
    assert extract_posed_challenge("2 treats plus 3 berries makes...") == (2, 3)


def test_extract_posed_challenge_recognizes_the_more_shape():
    assert extract_posed_challenge(
        "If you have 2 chocolates and you get 3 more, how many would you have?"
    ) == (2, 3)


def test_extract_posed_challenge_ignores_an_earlier_unrelated_number():
    """Found live: a correction reply can mention the correct sum
    before restating the original problem ("...you would actually
    have 5 chocolates! So what if we counted them together: 2, then 3
    more.") -- the real operands (2, 3) must win, not a stray 5."""
    text = (
        "That's a good try, but remember that if you start with 2 "
        "chocolates and add 3 more, you would actually have 5 "
        "chocolates! So what if we counted them together: 2, then 3 "
        "more. Can you count them out loud for me?"
    )
    assert extract_posed_challenge(text) == (2, 3)


def test_extract_posed_challenge_returns_none_for_ordinary_conversation():
    assert extract_posed_challenge("Milk chocolate is so yummy and creamy!") is None


def test_extract_bare_number_reads_a_single_number():
    assert extract_bare_number("4. Chocolates") == 4
    assert extract_bare_number("I think it's 5.") == 5


def test_extract_bare_number_takes_the_last_number_when_counting_aloud():
    assert extract_bare_number("1, 2, 3, 4, 5.") == 5


def test_extract_bare_number_returns_none_when_no_number_present():
    assert extract_bare_number("Dogs are cool") is None
