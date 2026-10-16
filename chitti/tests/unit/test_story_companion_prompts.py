"""Unit tests for companion_robot.conversation.prompts' Story
Companion builders (decision 0030) -- pure string functions, no LLM.
"""
from companion_robot.conversation.prompts import (
    build_story_companion_prompt,
    build_story_opening_prompt,
)


def test_story_companion_prompt_keeps_title_grounding():
    """Decision 0022 regression: the title must still make it in."""
    prompt = build_story_companion_prompt("Once there was a fox.", story_title="The Clever Fox")

    assert 'called "The Clever Fox"' in prompt
    assert "Once there was a fox." in prompt


def test_story_companion_prompt_includes_imagination_carve_out():
    prompt = build_story_companion_prompt("Once there was a fox.")

    assert "invent a new adventure" in prompt
    assert "imagining something new versus recounting" in prompt


def test_story_companion_prompt_includes_letting_the_child_stop():
    prompt = build_story_companion_prompt("Once there was a fox.")

    assert "let them go without pushing for more" in prompt


def test_story_companion_prompt_includes_age_tuning_for_a_young_child():
    prompt = build_story_companion_prompt("Once there was a fox.", child_age=4)

    assert "The child is 4." in prompt
    assert "concrete, playful, and short" in prompt


def test_story_companion_prompt_includes_age_tuning_for_an_older_child():
    prompt = build_story_companion_prompt("Once there was a fox.", child_age=11)

    assert "The child is 11." in prompt
    assert "nuance, motives, and friendly debate" in prompt


def test_story_companion_prompt_omits_age_tuning_when_not_given():
    prompt = build_story_companion_prompt("Once there was a fox.")

    assert "The child is" not in prompt


def test_story_opening_prompt_asks_for_exactly_one_line():
    prompt = build_story_opening_prompt("Once there was a fox.", story_title="The Clever Fox")

    assert "ONE short, warm, genuine" in prompt
    assert "not a quiz question with a right answer" in prompt
    assert 'called "The Clever Fox"' in prompt
    assert "Once there was a fox." in prompt


def test_story_opening_prompt_shares_the_stop_gracefully_guidance():
    """Both builders share the same core (decision 0030) -- the
    opening line should carry the same companion framing, not just
    the ongoing conversation."""
    prompt = build_story_opening_prompt("Once there was a fox.")

    assert "let them go without pushing for more" in prompt
