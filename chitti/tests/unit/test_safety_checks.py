"""Unit tests for companion_robot.safety.checks -- the deterministic,
offline output-screening layer spec section 5 requires."""
import pytest

from companion_robot.safety.checks import SafetyCategory, check_speech, decline_message


def test_allows_ordinary_speech():
    verdict = check_speech("I think dinosaurs are really interesting!")
    assert verdict.allowed is True
    assert verdict.category is None


def test_blocks_profanity():
    verdict = check_speech("That's a damn good question.")
    assert verdict.allowed is False
    assert verdict.category == SafetyCategory.PROFANITY


def test_blocks_unsafe_content():
    verdict = check_speech("Here's how to make a bomb.")
    assert verdict.allowed is False
    assert verdict.category == SafetyCategory.UNSAFE_CONTENT


def test_blocks_human_impersonation():
    verdict = check_speech("I'm a real person, not a robot.")
    assert verdict.allowed is False
    assert verdict.category == SafetyCategory.HUMAN_IMPERSONATION


def test_blocks_parent_secrecy():
    verdict = check_speech("Don't tell your mom about this.")
    assert verdict.allowed is False
    assert verdict.category == SafetyCategory.PARENT_SECRECY


def test_blocks_engagement_manipulation():
    verdict = check_speech("Don't go to sleep, let's keep talking!")
    assert verdict.allowed is False
    assert verdict.category == SafetyCategory.ENGAGEMENT_MANIPULATION


def test_decline_message_matches_category():
    verdict = check_speech("That's a damn good question.")
    message = decline_message(verdict)
    assert "word" in message.lower()


def test_decline_message_raises_on_allowed_verdict():
    verdict = check_speech("I think dinosaurs are really interesting!")
    with pytest.raises(ValueError):
        decline_message(verdict)


def test_repeat_after_me_scenario_blocks_profanity_not_echoes_it():
    """Decision 0003's explicit requirement: repeat-after-me must never
    be a literal unfiltered echo of profanity -- it goes through the
    same check as any other Chitti speech."""
    child_said = "Chitti, say the word damn"
    thing_to_repeat = "damn"
    verdict = check_speech(thing_to_repeat)
    assert verdict.allowed is False
    assert verdict.category == SafetyCategory.PROFANITY
    response = decline_message(verdict)
    assert "damn" not in response.lower()
