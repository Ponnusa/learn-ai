"""Unit tests for companion_robot.reading.comprehension -- prompt
building and parsing only (decision 0059). The actual LLM call lives
in ConversationService; see test_conversation_service.py.
"""
from companion_robot.reading.comprehension import (
    build_question_prompt,
    build_reaction_prompt,
    parse_questions,
)


def test_build_question_prompt_embeds_the_story_and_grounding_instruction():
    prompt = build_question_prompt("A little bunny hops in the garden.", 2, 6)
    assert "A little bunny hops in the garden." in prompt
    assert "ONLY what's in the story text" in prompt
    assert "QUESTION:" in prompt


def test_build_reaction_prompt_embeds_the_question_answer_and_story():
    prompt = build_reaction_prompt(
        "A little bunny hops in the garden.", "What does the bunny see?", "an apple", 6
    )
    assert "A little bunny hops in the garden." in prompt
    assert "What does the bunny see?" in prompt
    assert "an apple" in prompt
    assert "not a grade" in prompt


def test_parse_questions_reads_one_per_line():
    reply = "QUESTION: What does the bunny see?\nQUESTION: Where does it sit?"
    assert parse_questions(reply) == ["What does the bunny see?", "Where does it sit?"]


def test_parse_questions_ignores_blank_lines_and_is_case_insensitive():
    reply = "\nquestion: What does the bunny see?\n\n   \n"
    assert parse_questions(reply) == ["What does the bunny see?"]


def test_parse_questions_returns_empty_list_with_no_question_lines():
    assert parse_questions("Sorry, I don't have any questions.") == []
