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

from companion_robot.education.math_check import MathCheckResult
from companion_robot.safety.checks import SafetyCategory, check_speech, decline_message
from companion_robot.voice.interfaces import LanguageModelBackend

from .prompts import (
    INTENT_CLASSIFIER_SYSTEM_PROMPT,
    SESSION_SUMMARY_SYSTEM_PROMPT,
    TEACHABLE_FRIEND_SYSTEM_PROMPT,
    build_everyday_companion_prompt,
    build_math_check_note,
    build_story_companion_prompt,
    build_story_opening_prompt,
    build_welcome_back_prompt,
)

_KNOWN_INTENT_LABELS = {"STORY", "SONG", "CHAT", "TEACH"}


@dataclass
class ConversationResult:
    text: str
    blocked: bool
    category: SafetyCategory | None = None


class ConversationService:
    def __init__(
        self,
        llm: LanguageModelBackend,
        summarizer_llm: LanguageModelBackend | None = None,
        classifier_llm: LanguageModelBackend | None = None,
    ) -> None:
        self._llm = llm
        # Decision 0018: lets session summarization/welcome-back use a
        # different backend than live conversation (the product owner
        # specifically wants Claude for this), without forcing every
        # caller to use two backends if they don't need to.
        self._summarizer_llm = summarizer_llm or llm
        # Decision 0047: classify_intent() asks for exactly one word --
        # found live it was still taking 5.19s on the main conversational
        # backend's much larger token budget. A caller that wants that
        # call tightly capped (e.g. max_tokens=10) passes its own
        # instance here; defaults to the main llm, same optional-second-
        # backend pattern summarizer_llm already uses.
        self._classifier_llm = classifier_llm or llm

    async def teachable_friend_reply(
        self,
        messages: list[dict],
        math_check: MathCheckResult | None = None,
        already_tried: bool = False,
    ) -> ConversationResult:
        system_prompt = TEACHABLE_FRIEND_SYSTEM_PROMPT
        if math_check is not None:
            system_prompt += "\n\n" + build_math_check_note(math_check, already_tried)
        reply_text, _model = await self._llm.generate_reply(messages, system_prompt)
        return self._screen(reply_text)

    async def everyday_companion_reply(
        self,
        messages: list[dict],
        math_check: MathCheckResult | None = None,
        already_tried: bool = False,
        child_age: int | None = None,
    ) -> ConversationResult:
        """Decision 0034: the third mode for everyday chat, play, and
        curiosity -- same math_check reuse as teachable_friend_reply()
        so a stray "2 plus 2 is 4" during casual chat still gets
        verified, without duplicating that logic."""
        system_prompt = build_everyday_companion_prompt(child_age)
        if math_check is not None:
            system_prompt += "\n\n" + build_math_check_note(math_check, already_tried)
        reply_text, _model = await self._llm.generate_reply(messages, system_prompt)
        return self._screen(reply_text)

    async def story_companion_reply(
        self,
        messages: list[dict],
        story_transcript: str,
        story_title: str | None = None,
        child_age: int | None = None,
    ) -> ConversationResult:
        system_prompt = build_story_companion_prompt(story_transcript, story_title, child_age)
        reply_text, _model = await self._llm.generate_reply(messages, system_prompt)
        return self._screen(reply_text)

    async def story_opening_invitation(
        self,
        story_transcript: str,
        story_title: str | None = None,
        child_age: int | None = None,
    ) -> ConversationResult:
        """Decision 0030: found live -- Chitti read the story and then
        went silent, waiting for the child to speak first. One
        generated opening line instead, same one-shot pattern as
        welcome_back_greeting() (a synthetic trigger message, since
        generate_reply() needs at least one)."""
        prompt = build_story_opening_prompt(story_transcript, story_title, child_age)
        reply_text, _model = await self._llm.generate_reply(
            [{"role": "user", "content": "The story just ended."}], prompt
        )
        return self._screen(reply_text)

    async def classify_intent(self, text: str) -> str | None:
        """Decision 0042's LLM fallback for mode-switch detection --
        only called (from voice_loop_demo.py) when intent/router.py's
        deterministic phrases don't match a known switch request but
        the turn at least mentions an activity keyword. One cheap
        classification call, not a conversational reply, so its output
        is never spoken and deliberately not screened through
        check_speech() -- same reasoning summarize_session() already
        uses for its own non-spoken LLM call."""
        reply_text, _model = await self._classifier_llm.generate_reply(
            [{"role": "user", "content": text}], INTENT_CLASSIFIER_SYSTEM_PROMPT
        )
        label = reply_text.strip().upper().split()[0] if reply_text.strip() else ""
        return label if label in _KNOWN_INTENT_LABELS else None

    def repeat_after_me(self, text: str) -> ConversationResult:
        """No LLM call -- the child's own words are screened and either
        echoed back verbatim or declined. Decision 0003: never a literal
        unfiltered echo."""
        return self._screen(text)

    async def summarize_session(self, transcript_lines: list[str]) -> str:
        """One cheap call at session end (decision 0018) -- not
        screened through check_speech(), since this is never spoken
        directly; only welcome_back_greeting()'s output (built from
        this) is. Returns "" for an empty transcript or when the
        summarizer finds nothing worth keeping."""
        if not transcript_lines:
            return ""
        reply_text, _model = await self._summarizer_llm.generate_reply(
            [{"role": "user", "content": "\n".join(transcript_lines)}],
            SESSION_SUMMARY_SYSTEM_PROMPT,
        )
        summary = reply_text.strip()
        return "" if summary.upper() == "NOTHING" else summary

    async def welcome_back_greeting(self, child_name: str, summary: str) -> ConversationResult:
        """The greeting spoken when a session starts and a prior
        session's summary exists. Screened like any other Chitti
        speech -- a summary echoing something unsafe the child said
        last time must not make it into this greeting unfiltered."""
        prompt = build_welcome_back_prompt(child_name, summary)
        reply_text, _model = await self._summarizer_llm.generate_reply(
            [{"role": "user", "content": "Say hello."}], prompt
        )
        return self._screen(reply_text)

    def _screen(self, text: str) -> ConversationResult:
        verdict = check_speech(text)
        if not verdict.allowed:
            return ConversationResult(
                text=decline_message(verdict), blocked=True, category=verdict.category
            )
        return ConversationResult(text=text, blocked=False, category=None)
