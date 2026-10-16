"""Unit tests for voice_loop_demo.py's _resolve_math_check() (decision
0025), _update_challenge_state() (decision 0027), and
_patch_if_still_unresolved() (decision 0029) -- pure functions, no
I/O, no real LLM needed.
"""
from companion_robot.conversation.service import ConversationResult
from companion_robot.education.math_check import build_result
from companion_robot.voice_loop_demo import (
    _patch_if_still_unresolved,
    _resolve_math_check,
    _update_challenge_state,
)


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


def test_stops_rearming_past_the_incorrect_streak_cap():
    """Found live (decision 0028): past a couple of tries at the same
    problem, the child tends to shift from answering the sum to
    explaining their own counting method -- continuing to re-arm just
    produces increasingly irrelevant "still wrong" notes about numbers
    that don't actually mean a claimed total. This turn's own
    math_check/note still applies as normal (already_tried should
    still be True); only the *next* round is skipped."""
    incorrect = build_result(5, 2, claimed_sum=8)

    # third consecutive incorrect result for the same problem
    pending_challenge, streak = _update_challenge_state(incorrect, incorrect_streak=2)

    assert pending_challenge is None  # stop re-arming for next turn
    assert streak == 3
    assert streak > 1  # this turn's own note should still escalate


def test_no_check_at_all_clears_the_pending_challenge_and_streak():
    pending_challenge, streak = _update_challenge_state(None, incorrect_streak=1)

    assert pending_challenge is None
    assert streak == 0


def test_patch_appends_the_correct_answer_when_the_reply_only_hedges():
    """Found live (decision 0029): "I can see why you'd say it's 8
    that way!" isn't a clean restated wrong equation -- just vague
    agreement with no number stated at all. Must still get patched."""
    math_check = build_result(5, 2, claimed_sum=8)
    result = ConversationResult(text="I can see why you'd say it's 8 that way!", blocked=False)

    patched = _patch_if_still_unresolved(result, math_check, already_tried=True)

    assert "the answer is 7" in patched.text


def test_patch_appends_when_the_reply_restates_the_wrong_sum():
    math_check = build_result(5, 2, claimed_sum=8)
    result = ConversationResult(text="So 5 plus 2 is 8, got it!", blocked=False)

    patched = _patch_if_still_unresolved(result, math_check, already_tried=True)

    assert "the answer is 7" in patched.text


def test_patch_leaves_a_correct_reply_alone():
    math_check = build_result(5, 2, claimed_sum=8)
    result = ConversationResult(
        text="Actually it would be 6 and 7, so the total is still 7!", blocked=False
    )

    patched = _patch_if_still_unresolved(result, math_check, already_tried=True)

    assert patched.text == "Actually it would be 6 and 7, so the total is still 7!"


def test_patch_does_nothing_on_a_first_attempt_not_yet_escalated():
    """Asking for an explanation without yet stating the answer is
    the CORRECT first-attempt behavior (decision 0025) -- the patch
    must not fire just because the correct number isn't mentioned
    yet."""
    math_check = build_result(5, 2, claimed_sum=8)
    result = ConversationResult(text="Can you show me how you counted that?", blocked=False)

    patched = _patch_if_still_unresolved(result, math_check, already_tried=False)

    assert patched.text == "Can you show me how you counted that?"


def test_patch_does_nothing_when_math_check_is_correct_or_absent():
    correct = build_result(5, 2, claimed_sum=7)
    result = ConversationResult(text="Nice counting!", blocked=False)

    assert _patch_if_still_unresolved(result, correct, already_tried=True).text == "Nice counting!"
    assert _patch_if_still_unresolved(result, None, already_tried=True).text == "Nice counting!"


def test_patch_never_touches_a_blocked_reply():
    math_check = build_result(5, 2, claimed_sum=8)
    result = ConversationResult(text="declined message", blocked=True)

    patched = _patch_if_still_unresolved(result, math_check, already_tried=True)

    assert patched.text == "declined message"
