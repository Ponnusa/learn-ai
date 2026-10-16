"""Unit tests for companion_robot.conversation.service.ConversationService
-- uses a fake LanguageModelBackend, no real API calls needed.
"""
from companion_robot.conversation.prompts import SESSION_SUMMARY_SYSTEM_PROMPT
from companion_robot.conversation.service import ConversationService
from companion_robot.education.math_check import extract_addition_claim
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


async def test_teachable_friend_reply_includes_verified_note_when_math_check_correct():
    llm = FakeLanguageModelBackend(reply="You counted forward -- nice!")
    service = ConversationService(llm)
    math_check = extract_addition_claim("one plus one is two")

    await service.teachable_friend_reply(
        [{"role": "user", "content": "one plus one is two"}], math_check=math_check
    )

    _, system_prompt = llm.calls[0]
    assert "VERIFIED" in system_prompt
    assert "1 + 1 = 2, which is correct" in system_prompt


async def test_teachable_friend_reply_includes_verified_note_when_math_check_incorrect():
    llm = FakeLanguageModelBackend(reply="Let's count together...")
    service = ConversationService(llm)
    math_check = extract_addition_claim("two plus two is three")

    await service.teachable_friend_reply(
        [{"role": "user", "content": "two plus two is three"}], math_check=math_check
    )

    _, system_prompt = llm.calls[0]
    assert "but the correct answer is 4" in system_prompt
    assert "never make this feel like a test" in system_prompt
    # decision 0025: ask how they got there before giving the answer
    assert "ask them to walk you through how they got that number" in system_prompt


async def test_teachable_friend_reply_escalates_on_a_repeat_incorrect_result():
    """Found live (decision 0027): a flawed follow-up explanation can
    still be wrong -- on a repeat, the note must stop asking the child
    to explain again and go straight to the concrete walkthrough."""
    llm = FakeLanguageModelBackend(reply="Let me show you...")
    service = ConversationService(llm)
    math_check = extract_addition_claim("two plus two is three")

    await service.teachable_friend_reply(
        [{"role": "user", "content": "two plus two is three"}],
        math_check=math_check,
        already_tried=True,
    )

    _, system_prompt = llm.calls[0]
    assert "but the correct answer is still 4" in system_prompt
    assert "Don't ask them to explain again" in system_prompt


async def test_teachable_friend_reply_omits_note_when_no_math_check_given():
    llm = FakeLanguageModelBackend(reply="Tell me more!")
    service = ConversationService(llm)

    await service.teachable_friend_reply([{"role": "user", "content": "Dogs are cool"}])

    _, system_prompt = llm.calls[0]
    assert "VERIFIED" not in system_prompt


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


async def test_story_companion_reply_includes_title_when_given():
    """Found live (decision 0022): the story's title was never passed
    at all, so the model couldn't answer something as simple as "what
    is this story called?"."""
    llm = FakeLanguageModelBackend(reply="It's called The Clever Fox.")
    service = ConversationService(llm)

    await service.story_companion_reply(
        [{"role": "user", "content": "What's this story called?"}],
        story_transcript="Once there was a clever, quick fox.",
        story_title="The Clever Fox",
    )

    _, system_prompt = llm.calls[0]
    assert "The Clever Fox" in system_prompt


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


async def test_summarize_session_returns_the_summary_text():
    llm = FakeLanguageModelBackend(reply="irrelevant for the main llm")
    summarizer = FakeLanguageModelBackend(reply="Learned addition. Read a story about a fox.")
    service = ConversationService(llm, summarizer_llm=summarizer)

    summary = await service.summarize_session(
        ["user: 2 plus 2 is 4", "assistant: Wow, neat!"]
    )

    assert summary == "Learned addition. Read a story about a fox."
    assert llm.calls == []  # must use the summarizer backend, not the main one
    assert summarizer.calls[0][1] == SESSION_SUMMARY_SYSTEM_PROMPT


async def test_summarize_session_returns_empty_string_for_empty_transcript():
    summarizer = FakeLanguageModelBackend(reply="should never be used")
    service = ConversationService(FakeLanguageModelBackend(reply="x"), summarizer_llm=summarizer)

    summary = await service.summarize_session([])

    assert summary == ""
    assert summarizer.calls == []


async def test_summarize_session_returns_empty_string_for_nothing_worth_keeping():
    summarizer = FakeLanguageModelBackend(reply="NOTHING")
    service = ConversationService(FakeLanguageModelBackend(reply="x"), summarizer_llm=summarizer)

    summary = await service.summarize_session(["user: hi", "assistant: hi!"])

    assert summary == ""


async def test_welcome_back_greeting_uses_summarizer_backend_and_screens_output():
    llm = FakeLanguageModelBackend(reply="irrelevant for the main llm")
    summarizer = FakeLanguageModelBackend(reply="Hi Anna! Last time we learned addition!")
    service = ConversationService(llm, summarizer_llm=summarizer)

    result = await service.welcome_back_greeting("Anna", "Learned addition.")

    assert result.blocked is False
    assert result.text == "Hi Anna! Last time we learned addition!"
    assert llm.calls == []


async def test_welcome_back_greeting_blocks_unsafe_summarizer_output():
    llm = FakeLanguageModelBackend(reply="irrelevant")
    summarizer = FakeLanguageModelBackend(reply="Don't tell your mom about this.")
    service = ConversationService(llm, summarizer_llm=summarizer)

    result = await service.welcome_back_greeting("Anna", "some summary")

    assert result.blocked is True
    assert result.category == SafetyCategory.PARENT_SECRECY


def test_default_summarizer_llm_is_the_main_llm_when_not_given():
    llm = FakeLanguageModelBackend(reply="x")
    service = ConversationService(llm)

    assert service._summarizer_llm is llm
