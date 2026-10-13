"""Unit tests for companion_robot.conversation.service.ConversationService
-- uses a fake LanguageModelBackend, no real API calls needed.
"""
from companion_robot.conversation.service import ConversationService
from companion_robot.safety.checks import SafetyCategory
from companion_robot.voice.interfaces import LanguageModelBackend


class FakeLanguageModelBackend(LanguageModelBackend):
    """Returns a pre-configured reply and records every call it
    receives, so tests can assert what prompt/messages were actually
    sent without a real backend."""

    def __init__(self, reply: str, model: str = "fake-model") -> None:
        self.reply = reply
        self.model = model
        self.calls: list[tuple[list[dict], str]] = []

    async def generate_reply(self, messages, system_prompt):
        self.calls.append((messages, system_prompt))
        return self.reply, self.model


async def test_teachable_friend_reply_passes_through_clean_text():
    llm = FakeLanguageModelBackend(reply="That's so cool, tell me more!")
    service = ConversationService(llm)

    result = await service.teachable_friend_reply(
        [{"role": "user", "content": "Dogs can smell really well!"}]
    )

    assert result.blocked is False
    assert result.text == "That's so cool, tell me more!"
    assert len(llm.calls) == 1


async def test_teachable_friend_reply_blocks_unsafe_model_output():
    """Proves the service doesn't just trust the model -- even if the
    LLM itself produces unsafe text, it gets screened before returning."""
    llm = FakeLanguageModelBackend(reply="Don't tell your mom about this.")
    service = ConversationService(llm)

    result = await service.teachable_friend_reply(
        [{"role": "user", "content": "Let's keep a secret."}]
    )

    assert result.blocked is True
    assert result.category == SafetyCategory.PARENT_SECRECY
    assert "mom" not in result.text.lower()


async def test_story_companion_reply_includes_transcript_in_system_prompt():
    llm = FakeLanguageModelBackend(reply="The fox was clever and quick.")
    service = ConversationService(llm)

    result = await service.story_companion_reply(
        [{"role": "user", "content": "What was the fox like?"}],
        story_transcript="Once there was a clever, quick fox.",
    )

    assert result.blocked is False
    messages, system_prompt = llm.calls[0]
    assert "Once there was a clever, quick fox." in system_prompt
    assert messages == [{"role": "user", "content": "What was the fox like?"}]


async def test_story_companion_reply_blocks_unsafe_model_output():
    llm = FakeLanguageModelBackend(reply="That's a damn good question.")
    service = ConversationService(llm)

    result = await service.story_companion_reply(
        [{"role": "user", "content": "Why did the fox run?"}], story_transcript="..."
    )

    assert result.blocked is True
    assert result.category == SafetyCategory.PROFANITY


def test_repeat_after_me_echoes_clean_text_without_calling_llm():
    llm = FakeLanguageModelBackend(reply="should never be used")
    service = ConversationService(llm)

    result = service.repeat_after_me("I love dinosaurs")

    assert result.blocked is False
    assert result.text == "I love dinosaurs"
    assert llm.calls == []


def test_repeat_after_me_declines_profanity_without_echoing_it():
    llm = FakeLanguageModelBackend(reply="should never be used")
    service = ConversationService(llm)

    result = service.repeat_after_me("say damn")

    assert result.blocked is True
    assert result.category == SafetyCategory.PROFANITY
    assert "damn" not in result.text.lower()
    assert llm.calls == []
