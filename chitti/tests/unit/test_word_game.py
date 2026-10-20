"""Unit tests for companion_robot.reading.word_game -- the post-
reading "missing letters" bonus game (decision 0057). Pure, no LLM,
not part of the mastery-grading pipeline.
"""
from companion_robot.reading.word_game import (
    blank_vowels,
    incorrect_response,
    is_correct_answer,
    pick_game_words,
    random_closing_line,
    random_correct_response,
    spell_out_blanked,
)


def test_pick_game_words_skips_short_and_vowel_less_words():
    words = ["A", "cat", "sat", "in", "the", "garden"]
    picked = pick_game_words(words)
    assert "a" not in picked
    assert "in" not in picked  # 2 letters, below the minimum


def test_pick_game_words_picks_the_longest_qualifying_words():
    words = ["a", "little", "bunny", "hops", "in", "the", "garden"]
    picked = pick_game_words(words, max_words=2)
    assert picked == ["little", "garden"]  # 6 letters each, longest


def test_pick_game_words_dedupes_repeated_words():
    words = ["garden", "garden", "garden"]
    picked = pick_game_words(words, max_words=5)
    assert picked == ["garden"]


def test_pick_game_words_returns_empty_when_nothing_qualifies():
    assert pick_game_words(["a", "I", "in", "is"]) == []


def test_blank_vowels_matches_the_japan_example():
    assert blank_vowels("japan") == "j_p_n"


def test_blank_vowels_keeps_a_doubled_consonant_intact():
    # "apple": a(V) pp(C, doubled) l(C) e(V) -- only the vowels blank.
    assert blank_vowels("apple") == "_ppl_"


def test_blank_vowels_treats_a_vowel_team_as_one_unit():
    """"boat"'s "oa" is a single vowel-team grapheme -- both letters
    blank together, not independently, the phonics-correct
    granularity for this curriculum."""
    assert blank_vowels("boat") == "b__t"


def test_spell_out_blanked_is_speakable():
    assert spell_out_blanked("j_p_n") == "J, blank, P, blank, N"


def test_is_correct_answer_matches_the_word_alone():
    assert is_correct_answer("japan", "japan") is True


def test_is_correct_answer_matches_the_word_embedded_in_a_longer_reply():
    assert is_correct_answer("japan", "I think it's Japan!") is True


def test_is_correct_answer_is_false_when_the_word_is_never_said():
    assert is_correct_answer("japan", "ummm not sure") is False


def test_random_correct_response_is_never_empty():
    assert random_correct_response()


def test_incorrect_response_names_the_word():
    assert '"sat"' in incorrect_response("sat")


def test_incorrect_response_includes_a_phonics_breakdown():
    """Decision 0070: found live -- a missed word in this game got
    nothing but the answer handed over, with zero phonics explanation,
    unlike the hint ladder's own graduated breakdown. A wrong guess now
    gets the same sound-by-sound teaching moment."""
    response = incorrect_response("frog")
    assert "'f' like in 'fish'" in response
    assert "'o' like in 'dog'" in response


def test_random_closing_line_is_never_empty():
    assert random_closing_line()
