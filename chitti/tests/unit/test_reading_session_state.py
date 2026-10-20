"""Unit tests for companion_robot.reading.session_state -- the
Reading Partner v2 state machine (decision 0075). Pure, no I/O."""
from companion_robot.reading.session_state import (
    CLEAN_READ_ACCURACY,
    MAX_PRACTICE_WORDS,
    ReadingState,
    SentenceSession,
    seems_like_a_help_request,
    seems_like_a_stop_request,
)


def _session(sentence: str = "A cat sat.") -> SentenceSession:
    return SentenceSession(sentence=sentence)


def test_new_session_starts_at_intro():
    session = _session()
    assert session.state == ReadingState.INTRO


def test_record_attempt_grades_against_the_sentence_and_remembers_it():
    session = _session("A cat sat.")
    result = session.record_attempt("a cat sat", duration_seconds=3.0)
    assert result.accuracy == 1.0
    assert session.attempts == [result]


def test_clean_first_read_skips_straight_to_comprehension():
    session = _session("A cat sat.")
    result = session.record_attempt("a cat sat", duration_seconds=3.0)
    assert result.accuracy >= CLEAN_READ_ACCURACY
    assert session.decide_after_first_read(result) == ReadingState.COMPREHENSION
    assert session.state == ReadingState.COMPREHENSION


def test_rough_first_read_moves_to_model_read():
    session = _session("A cat sat.")
    result = session.record_attempt("a dog ran", duration_seconds=3.0)
    assert result.accuracy < CLEAN_READ_ACCURACY
    assert session.decide_after_first_read(result) == ReadingState.MODEL_READ
    assert session.state == ReadingState.MODEL_READ


def test_second_read_with_real_misses_moves_to_word_practice():
    session = _session("A cat sat.")
    result = session.record_attempt("a dog sat", duration_seconds=3.0)  # "cat" missed
    assert session.decide_after_second_read(result) == ReadingState.WORD_PRACTICE
    assert session.practice_words == ["cat"]


def test_second_read_with_no_real_misses_skips_word_practice():
    session = _session("A cat sat.")
    result = session.record_attempt("a cat sat", duration_seconds=3.0)
    assert session.decide_after_second_read(result) == ReadingState.COMPREHENSION
    assert session.practice_words == []


def test_second_read_caps_practice_words_at_the_limit():
    session = _session("The little purple garden grew yellow flowers.")
    result = session.record_attempt(
        "the silly gotten mellow orchid bandana flowers", duration_seconds=5.0
    )
    session.decide_after_second_read(result)
    assert len(session.practice_words) <= MAX_PRACTICE_WORDS


def test_finish_word_practice_moves_to_final_reread():
    session = _session()
    session.state = ReadingState.WORD_PRACTICE
    assert session.finish_word_practice() == ReadingState.FINAL_REREAD


def test_finish_final_reread_moves_to_comprehension():
    session = _session()
    session.state = ReadingState.FINAL_REREAD
    assert session.finish_final_reread() == ReadingState.COMPREHENSION


def test_complete_is_terminal():
    session = _session()
    assert session.complete() == ReadingState.COMPLETE


def test_seems_like_a_help_request_on_empty_text():
    assert seems_like_a_help_request("") is True
    assert seems_like_a_help_request("   ") is True


def test_seems_like_a_help_request_on_explicit_ask():
    assert seems_like_a_help_request("read with me") is True
    assert seems_like_a_help_request("can you help me") is True


def test_seems_like_a_help_request_is_false_for_a_real_attempt():
    assert seems_like_a_help_request("a cat sat") is False


def test_seems_like_a_stop_request_on_explicit_phrases():
    assert seems_like_a_stop_request("I'm done, this is too hard") is True
    assert seems_like_a_stop_request("stop") is True


def test_seems_like_a_stop_request_is_false_for_a_real_attempt():
    assert seems_like_a_stop_request("a cat sat") is False
