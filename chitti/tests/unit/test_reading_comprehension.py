"""Unit tests for companion_robot.reading.comprehension -- prompt
building and parsing only (decisions 0059/0062). The actual LLM call
lives in ConversationService; see test_conversation_service.py.
"""
from companion_robot.reading.comprehension import (
    answer_matches_story_text,
    build_question_prompt,
    build_reaction_prompt,
    build_word_meaning_question_prompt,
    parse_comprehension_reaction,
    parse_questions,
)


def test_build_question_prompt_embeds_the_story_and_grounding_instruction():
    prompt = build_question_prompt("A little bunny hops in the garden.", 2, 6)
    assert "A little bunny hops in the garden." in prompt
    assert "ONLY what's in the story text" in prompt
    assert "QUESTION:" in prompt


def test_build_word_meaning_question_prompt_embeds_the_sentence_and_word():
    """Decision 0074: checks understanding of a word's meaning/role in
    the sentence it was just hinted in, not whether it was decoded."""
    prompt = build_word_meaning_question_prompt("The frog jumps over the log.", "frog", 6)
    assert "The frog jumps over the log." in prompt
    assert '"frog"' in prompt
    assert "ONLY what's in the sentence" in prompt
    assert "QUESTION:" in prompt


def test_build_reaction_prompt_embeds_the_question_answer_and_story():
    prompt = build_reaction_prompt(
        "A little bunny hops in the garden.", "What does the bunny see?", "an apple", 6
    )
    assert "A little bunny hops in the garden." in prompt
    assert "What does the bunny see?" in prompt
    assert "an apple" in prompt
    assert "STATUS:" in prompt and "SAY:" in prompt


def test_build_reaction_prompt_withholds_the_answer_before_the_last_attempt():
    """Decision 0062, found live: the original prompt revealed the
    correct detail immediately on a wrong answer. Any attempt before
    the last must instead ask for a clue-and-retry, not a reveal."""
    prompt = build_reaction_prompt("story", "q", "a", 6, attempt_number=1, max_attempts=2)
    assert "do NOT reveal the correct" in prompt
    assert "ONE small clue" in prompt


def test_build_reaction_prompt_resolves_on_the_last_attempt():
    prompt = build_reaction_prompt("story", "q", "a", 6, attempt_number=2, max_attempts=2)
    assert "last attempt" in prompt
    assert "do NOT ask them to try again" in prompt


def test_parse_comprehension_reaction_reads_needs_retry():
    reaction = parse_comprehension_reaction("STATUS: needs_retry\nSAY: Try once more!")
    assert reaction.needs_retry is True
    assert reaction.text == "Try once more!"


def test_parse_comprehension_reaction_reads_resolved():
    reaction = parse_comprehension_reaction("status: resolved\nsay: Great job!")
    assert reaction.needs_retry is False
    assert reaction.text == "Great job!"


def test_parse_comprehension_reaction_defaults_to_resolved_on_malformed_reply():
    """A parse hiccup must never leave the child stuck in a retry
    loop -- it defaults to moving on, and never says nothing."""
    reaction = parse_comprehension_reaction("not the expected format at all")
    assert reaction.needs_retry is False
    assert reaction.text  # never empty


def test_parse_questions_reads_one_per_line():
    reply = "QUESTION: What does the bunny see?\nQUESTION: Where does it sit?"
    assert parse_questions(reply) == ["What does the bunny see?", "Where does it sit?"]


def test_parse_questions_ignores_blank_lines_and_is_case_insensitive():
    reply = "\nquestion: What does the bunny see?\n\n   \n"
    assert parse_questions(reply) == ["What does the bunny see?"]


def test_parse_questions_returns_empty_list_with_no_question_lines():
    assert parse_questions("Sorry, I don't have any questions.") == []


# -- answer_matches_story_text (decision 0083) --


def test_answer_matches_story_text_true_for_a_literal_word_match():
    assert answer_matches_story_text("red", "Dan has a red dog.") is True


def test_answer_matches_story_text_true_for_a_multi_word_answer_with_one_shared_word():
    assert answer_matches_story_text("it was red", "Dan has a red dog.") is True


def test_answer_matches_story_text_false_when_nothing_shared():
    assert answer_matches_story_text("purple", "Dan has a red dog.") is False


def test_answer_matches_story_text_ignores_short_words_on_both_sides():
    # "a"/"is" are too short to count as a signal either way -- this
    # must not match just because both strings contain "a".
    assert answer_matches_story_text("a", "Dan has a red dog.") is False


def test_answer_matches_story_text_is_case_insensitive():
    assert answer_matches_story_text("RED", "Dan has a red dog.") is True
