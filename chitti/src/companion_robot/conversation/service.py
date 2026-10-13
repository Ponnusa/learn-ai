"""ConversationService (spec section 3.2.D): Teachable-Friend and Story
Companion, both screened through the Safety layer before anything is
returned to be spoken.

Every path here -- an LLM-generated Teachable-Friend reply, a
Story-Companion answer, or a repeat-after-me echo -- goes through the
same companion_robot.safety.checks.check_speech() call before the text
is considered sayable. No special-casing by source (decision 0003's
explicit requirement for repeat-after-me applies the same way to every
other path too).
"""
from dataclasses import dataclass

from companion_robot.safety.checks import SafetyCategory, check_speech, decline_message
from companion_robot.voice.interfaces import LanguageModelBackend

from .prompts import TEACHABLE_FRIEND_SYSTEM_PROMPT, build_story_companion_prompt


@dataclass
class ConversationResult:
    text: str
    blocked: bool
    category: SafetyCategory | None = None


class ConversationService:
    def __init__(self, llm: LanguageModelBackend) -> None:
        self._llm = llm

    async def teachable_friend_reply(self, messages: list[dict]) -> ConversationResult:
        reply_text, _model = await self._llm.generate_reply(
            messages, TEACHABLE_FRIEND_SYSTEM_PROMPT
        )
        return self._screen(reply_text)

    async def story_companion_reply(
        self, messages: list[dict], story_transcript: str
    ) -> ConversationResult:
        system_prompt = build_story_companion_prompt(story_transcript)
        reply_text, _model = await self._llm.generate_reply(messages, system_prompt)
        return self._screen(reply_text)

    def repeat_after_me(self, text: str) -> ConversationResult:
        """No LLM call -- the child's own words are screened and either
        echoed back verbatim or declined. Decision 0003: never a literal
        unfiltered echo."""
        return self._screen(text)

    def _screen(self, text: str) -> ConversationResult:
        verdict = check_speech(text)
        if not verdict.allowed:
            return ConversationResult(
                text=decline_message(verdict), blocked=True, category=verdict.category
            )
        return ConversationResult(text=text, blocked=False, category=None)
