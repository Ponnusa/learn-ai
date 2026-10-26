"""Unit tests for companion_robot.reading.word_game -- the post-
reading "missing letters" bonus game (decision 0057). Not part of the
mastery-grading pipeline; correctness itself is still decided here,
deterministically -- decision 0112 only moved the REACTION's phrasing
to one combined LLM call (ConversationService.react_to_word_game_answer(),
tested in test_conversation_service.py).
"""
from companion_robot.reading.word_game import (
    blank_vowels,
    build_word_game_reaction_prompt,
    find_word_occurrence,
    is_correct_answer,
    pick_game_words,
    random_closing_line,
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


def test_pick_game_words_skips_sight_words_even_when_long_enough():
    """Decision 0125, found live: "the" passed the old plain length
    check (3 letters, has a vowel to blank) and got picked, blanking
    to "th_" -- a nonsensical puzzle for a word meant to be recognized
    whole, not sounded out. Same bar hints.py's own
    is_worth_practicing() already applies for the hint ladder
    (decision 0058, the exact same word found live there too)."""
    words = ["pat", "has", "pup", "the", "can", "run", "and"]
    picked = pick_game_words(words, max_words=5)
    assert "the" not in picked


def test_blank_vowels_matches_the_japan_example():
    assert blank_vowels("japan") == "j_p_n"


def test_blank_vowels_preserves_the_original_casing():
    """Decision 0112: found live -- a story word's real capitalization
    (e.g. "Sam" starting a sentence) was lost because pick_game_words()
    only ever had the already-lowercased clean_word() copy to blank;
    the fix is blanking the word's own original-case text directly."""
    assert blank_vowels("Japan") == "J_p_n"
    assert blank_vowels("Sam") == "S_m"


def test_blank_vowels_keeps_a_doubled_consonant_intact():
    # "apple": a(V) pp(C, doubled) l(C) e(V) -- only the vowels blank.
    assert blank_vowels("apple") == "_ppl_"


def test_blank_vowels_treats_a_vowel_team_as_one_unit():
    """"boat"'s "oa" is a single vowel-team grapheme -- both letters
    blank together, not independently, the phonics-correct
    granularity for this curriculum."""
    assert blank_vowels("boat") == "b__t"


def test_is_correct_answer_matches_the_word_alone():
    assert is_correct_answer("japan", "japan") is True


def test_is_correct_answer_matches_the_word_embedded_in_a_longer_reply():
    assert is_correct_answer("japan", "I think it's Japan!") is True


def test_is_correct_answer_is_false_when_the_word_is_never_said():
    assert is_correct_answer("japan", "ummm not sure") is False


def test_random_closing_line_is_never_empty():
    assert random_closing_line()


def test_find_word_occurrence_locates_the_right_page_and_word_index():
    pages = ["Sam sat.", "Sam sat at the mat."]
    # The FIRST occurrence (page 0, not page 1) -- page_index=0,
    # word_index=1 (0-indexed: "Sam"=0, "sat."=1), original text
    # (with its trailing period) kept as-is.
    assert find_word_occurrence(pages, "sat") == (0, 1, "sat.")


def test_find_word_occurrence_preserves_original_casing():
    pages = ["Sam sat."]
    assert find_word_occurrence(pages, "sam") == (0, 0, "Sam")


def test_find_word_occurrence_returns_none_for_a_word_not_on_any_page():
    assert find_word_occurrence(["Sam sat."], "bunny") is None


def test_build_word_game_reaction_prompt_states_correctness_as_given_fact():
    """Decision 0112: correctness is decided by is_correct_answer()
    before this prompt is ever built -- the model is told, not asked,
    which words were right or wrong. Decision 0118: no phonics
    breakdown handed over for a wrong word any more -- just the real
    word itself, same as everywhere else in the reading flow since
    decision 0116."""
    prompt = build_word_game_reaction_prompt(
        "Sam sat at the mat.", [("sam", True), ("sat", False)], age=6
    )
    assert '"sam": correct.' in prompt
    assert '"sat": incorrect. The real word is "sat".' in prompt
    assert "like in" not in prompt  # no phonics breakdown
    assert "Sam sat at the mat." in prompt


def test_build_word_game_reaction_prompt_uses_singular_phrasing_for_one_word():
    prompt = build_word_game_reaction_prompt("Sam sat.", [("sam", True)], age=6)
    assert "a word hidden" in prompt
