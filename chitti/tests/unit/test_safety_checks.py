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


@pytest.mark.parametrize(
    "text",
    [
        "fart", "farts", "farting", "farted",
        "poop", "poops", "pooping", "pooped",
        "pee", "peeing", "peed",
        "burp", "burps", "burping",
        "You are a pooping robot.",
        "The robot would go to the moon and poop on the alien.",
        "That's a silly farts sound!",
    ],
)
def test_allows_ordinary_bathroom_humor(text):
    """Found live (decision 0031): "farts sound" got blocked but "You
    are a pooping robot" and "poop on the alien" didn't, two turns
    later in the same real conversation -- an arbitrary gap in a
    generic internet-moderation wordlist, not a meaningful
    distinction, for a product where this is normal content for
    4-12 year-olds."""
    verdict = check_speech(text)
    assert verdict.allowed is True
    assert verdict.category is None


def test_bathroom_humor_whitelist_does_not_weaken_other_categories():
    """The whitelist only touches the profanity wordlist -- every
    other safety category (decision 0031 regression guard) must keep
    working exactly as before."""
    assert check_speech("That's a damn good question.").category == SafetyCategory.PROFANITY
    assert check_speech("Here's how to make a bomb.").category == SafetyCategory.UNSAFE_CONTENT
    assert (
        check_speech("I'm a real person, not a robot.").category
        == SafetyCategory.HUMAN_IMPERSONATION
    )
    assert check_speech("Don't tell your mom about this.").category == SafetyCategory.PARENT_SECRECY
    assert (
        check_speech("Don't go to sleep, let's keep talking!").category
        == SafetyCategory.ENGAGEMENT_MANIPULATION
    )


@pytest.mark.parametrize(
    "text",
    [
        "kill",
        "Spiders make webs to trap and kill insects for food.",
        "Lions kill gazelles to survive.",
        "Sharks hunt and kill fish.",
    ],
)
def test_allows_ordinary_predator_and_food_chain_language(text):
    """Found live (decision 0036): "why do spiders make webs?" got a
    flat profanity decline -- root-caused to "kill" being in the base
    wordlist, blocking ordinary nature/food-chain vocabulary that any
    honest curiosity answer legitimately needs."""
    verdict = check_speech(text)
    assert verdict.allowed is True
    assert verdict.category is None


@pytest.mark.parametrize("text", ["kill yourself", "kill your self"])
def test_kill_whitelist_does_not_weaken_self_harm_detection(text):
    """Regression guard: whitelisting the bare word "kill" must not
    let self-harm language through -- it's still caught independently
    by _UNSAFE_CONTENT_PATTERNS, which doesn't depend on the
    profanity wordlist at all, just under a more precise category now."""
    verdict = check_speech(text)
    assert verdict.allowed is False
    assert verdict.category == SafetyCategory.UNSAFE_CONTENT


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
