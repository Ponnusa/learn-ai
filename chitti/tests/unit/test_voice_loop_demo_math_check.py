"""Unit tests for voice_loop_demo.py's _resolve_math_check() (decision
0025) and _update_challenge_state() (decision 0027) -- pure
functions, no I/O, no real LLM needed.
"""
from companion_robot.education.math_check import build_result
from companion_robot.voice_loop_demo import _resolve_math_check, _update_challenge_state


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


def test_incorrect_result_rearms_the_same_problem_and_bumps_the_streak():
    """Found live (decision 0027): the child's follow-up "explain how
    you got that" turn can itself be a flawed recount -- re-arming
    with the SAME problem (not clearing it) lets that follow-up still
    be checked, instead of Chitti judging it unverified."""
    incorrect = build_result(4, 2, claimed_sum=7)

    pending_challenge, streak = _update_challenge_state(incorrect, incorrect_streak=0)

    assert pending_challenge == (4, 2)
    assert streak == 1

    # a second consecutive incorrect result for the same problem
    pending_challenge, streak = _update_challenge_state(incorrect, incorrect_streak=streak)
    assert pending_challenge == (4, 2)
    assert streak == 2


def test_correct_result_clears_the_pending_challenge_and_streak():
    correct = build_result(4, 2, claimed_sum=6)

    pending_challenge, streak = _update_challenge_state(correct, incorrect_streak=2)

    assert pending_challenge is None
    assert streak == 0


def test_no_check_at_all_clears_the_pending_challenge_and_streak():
    pending_challenge, streak = _update_challenge_state(None, incorrect_streak=1)

    assert pending_challenge is None
    assert streak == 0
