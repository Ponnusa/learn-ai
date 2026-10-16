"""Unit tests for companion_robot.conversation.prompts.
build_everyday_companion_prompt() (decision 0034) -- pure string
function, no LLM.
"""
from companion_robot.conversation.prompts import (
    TEACHABLE_FRIEND_SYSTEM_PROMPT,
    build_everyday_companion_prompt,
)


def test_includes_casual_chat_guidance():
    prompt = build_everyday_companion_prompt()

    assert "chatting, playing, wondering about things together" in prompt
    assert "isn't a lesson" in prompt


def test_includes_simple_games_guidance():
    prompt = build_everyday_companion_prompt()

    assert "guess-the-animal" in prompt
    assert "change the rules partway through" in prompt


def test_includes_curiosity_say_not_sure_guidance():
    prompt = build_everyday_companion_prompt()

    assert "why do spiders make webs" in prompt
    assert "Say you're not sure rather than inventing a fact" in prompt


def test_includes_vary_conversational_moves():
    prompt = build_everyday_companion_prompt()

    assert "Don't end every single turn with a question" in prompt


def test_includes_concrete_brevity_example():
    """Decision 0037: found live -- the abstract "don't always ask"
    rule was already present but not reliably followed; added a
    concrete before/after example rather than restating the same
    abstract instruction a third time."""
    prompt = build_everyday_companion_prompt()

    assert "RROOAR" in prompt
    assert "a complete response doesn't need a question" in prompt


def test_includes_take_initiative_guidance():
    """Found live (decision 0037): Chitti asked "you go first, or
    should I start?" when the child's request to play was already
    clear enough to just begin."""
    prompt = build_everyday_companion_prompt()

    assert "just go ahead and start" in prompt
    assert "Only ask when you genuinely need something from them" in prompt


def test_includes_match_the_moment_guidance():
    prompt = build_everyday_companion_prompt()

    assert "Match how much you say to the moment" in prompt
    assert "keep quick game turns and reactions brief" in prompt


def test_includes_acknowledge_before_activity_guidance():
    """Found live (decision 0037): Chitti moved to offering games/
    jokes quickly after "nobody played with me today" instead of
    first giving room to share more."""
    prompt = build_everyday_companion_prompt()

    assert "acknowledge it first and give them room to say more" in prompt
    assert "don't rush straight into offering a game" in prompt


def test_includes_language_persistence_guidance():
    prompt = build_everyday_companion_prompt()

    assert "stay in that language until they switch back" in prompt
    assert "Don't correct their language choice, mixing, or an imperfect" in prompt


def test_includes_bilingual_guidance():
    """Decision 0035: don't leave Finnish/bilingual fully implicit --
    cheap and honest even though it's cosmetic until the separately
    deferred STT fix (decision 0020's English hardcoding) lands."""
    prompt = build_everyday_companion_prompt()

    assert "Follow whichever language the child uses" in prompt
    assert "Finnish" in prompt


def test_includes_trusted_adult_guidance():
    prompt = build_everyday_companion_prompt()

    assert "point them toward a parent or trusted adult" in prompt
    assert "never promise secrecy" in prompt


def test_includes_age_tuning_when_given():
    prompt = build_everyday_companion_prompt(child_age=6)

    assert "The child is 6." in prompt


def test_omits_age_tuning_when_not_given():
    prompt = build_everyday_companion_prompt()

    assert "The child is" not in prompt


def test_does_not_reuse_teachable_friend_wording():
    """Decision 0034's mode-shape decision: this is a separate
    prompt, not a rewrite of Teachable-Friend's "curious peer you
    teach me things" framing."""
    prompt = build_everyday_companion_prompt()

    assert prompt != TEACHABLE_FRIEND_SYSTEM_PROMPT
    assert "curious peer the child teaches" not in prompt
