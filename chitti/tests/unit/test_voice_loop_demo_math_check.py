"""Unit tests for voice_loop_demo.py's _resolve_math_check() (decision
0025) -- pure function, no I/O, no real LLM needed.
"""
from companion_robot.voice_loop_demo import _resolve_math_check


def test_a_self_stated_equation_always_wins_even_with_a_pending_challenge():
    result = _resolve_math_check("one plus one is two", pending_challenge=(2, 3))

    assert (result.a, result.b, result.claimed_sum) == (1, 1, 2)


def test_bare_number_reply_is_checked_against_the_pending_challenge():
    result = _resolve_math_check("4. Chocolates", pending_challenge=(2, 3))

    assert result.a == 2
    assert result.b == 3
    assert result.claimed_sum == 4
    assert result.correct_sum == 5
    assert result.correct is False


def test_correct_bare_number_reply_against_the_pending_challenge():
    result = _resolve_math_check("I think it's 5.", pending_challenge=(2, 3))

    assert result.correct is True


def test_counting_aloud_resolves_to_the_final_tally():
    result = _resolve_math_check("1, 2, 3, 4, 5.", pending_challenge=(2, 3))

    assert result.claimed_sum == 5
    assert result.correct is True


def test_no_pending_challenge_and_no_self_stated_equation_gives_no_check():
    assert _resolve_math_check("Dogs are cool", pending_challenge=None) is None


def test_pending_challenge_with_no_number_in_the_reply_gives_no_check():
    assert _resolve_math_check("I like them all equally", pending_challenge=(2, 3)) is None


def test_a_question_back_is_not_treated_as_an_answer():
    """Found live (decision 0026): "If we start at five and count two
    more numbers, what comes next?" is the child asking something
    back, not answering -- the trailing "two" isn't a claimed sum."""
    result = _resolve_math_check(
        "If we start at five and count two more numbers, what comes next?",
        pending_challenge=(5, 2),
    )

    assert result is None


def test_a_self_stated_equation_inside_a_question_still_counts():
    result = _resolve_math_check("two plus two is four, right?", pending_challenge=(5, 2))

    assert result is not None
    assert (result.a, result.b, result.claimed_sum) == (2, 2, 4)
