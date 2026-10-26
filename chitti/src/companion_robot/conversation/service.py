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
from companion_robot.reading.book_generation import (
    StoryDraft,
    generate_decodable_book,
    parse_story_draft,
)
from companion_robot.reading.comprehension import (
    LITERAL_MATCH_AFFIRMATION,
    ComprehensionReaction,
    answer_matches_story_text,
    build_question_prompt,
    build_reaction_prompt,
    parse_comprehension_reaction,
    parse_questions,
    sounds_like_a_retry_invitation,
)
from companion_robot.reading.schema import GeneratedBook, Objective
from companion_robot.reading.word_family import (
    build_family_prompt,
    extract_rime,
    parse_family_words,
    verify_family_word,
)
from companion_robot.reading.word_game import build_word_game_reaction_prompt
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

_KNOWN_INTENT_LABELS = {"STORY", "READ", "SONG", "CHAT", "TEACH"}

# Decision 0113: generate_word_family() asks for this many times the
# number of words it actually needs, since verify_family_word()'s own
# strict filter routinely drops some of what the LLM proposes.
_FAMILY_OVERREQUEST_FACTOR = 2


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

    async def generate_decodable_book(
        self,
        objective: Objective,
        *,
        interest: str = "",
        age: int = 6,
        sight_words=None,
        source_passage: str | None = None,
    ) -> GeneratedBook:
        """Decision 0051: the Reading Partner mode's verifier-gated book
        generator. Builds a real StoryProposer around this service's
        own llm and hands it to reading/book_generation.py's pure loop
        -- same propose/check-decodability/check_speech/retry shape as
        every other reading/ module, just with the real backend wired
        in instead of a test fake. Unlike every other path in this
        class, there's no single ConversationResult to return here --
        decodability and safety are enforced *inside* the generation
        loop itself (a violation is fed back and retried, not declined
        after the fact), so a GeneratedBook that comes back has always
        already passed check_speech() on every page.

        `source_passage` (decision 0068): a parent-uploaded exercise's
        own text the child just finished reading -- when given, themes
        the follow-up book on it instead of `interest`."""

        async def _propose(prompt: str) -> StoryDraft:
            reply_text, _model = await self._llm.generate_reply(
                [{"role": "user", "content": "Write the story now."}], prompt
            )
            return parse_story_draft(reply_text)

        return await generate_decodable_book(
            objective,
            proposer=_propose,
            sight_words=sight_words,
            interest=interest,
            age=age,
            source_passage=source_passage,
        )

    async def generate_comprehension_questions(
        self, story_text: str, num_questions: int = 2, age: int | None = None
    ) -> list[str]:
        """Decision 0059: 1-2 comprehension questions about the story
        just read -- including a parent-uploaded exercise (decision
        0052), a deliberate precedent change: that path otherwise
        never touches an LLM at all. Open-ended "why"/"what happened"
        questions have no single correct string to diff against, so
        unlike generate_decodable_book() there's no retry loop here --
        each candidate question is screened through check_speech()
        independently and a flagged one is simply dropped, not
        retried. Returns [] if every question gets dropped, so the
        caller skips the whole phase rather than blocking the reading
        session on it."""
        prompt = build_question_prompt(story_text, num_questions, age)
        reply_text, _model = await self._llm.generate_reply(
            [{"role": "user", "content": "Write the questions now."}], prompt
        )
        questions = parse_questions(reply_text)
        safe_questions = [q for q in questions if check_speech(q).allowed]
        return safe_questions[:num_questions]

    async def react_to_comprehension_answer(
        self,
        story_text: str,
        question: str,
        child_answer: str,
        age: int | None = None,
        *,
        attempt_number: int = 1,
        max_attempts: int = 2,
    ) -> ComprehensionReaction:
        """One short, warm, story-grounded reaction to what the child
        said. Decision 0062: before the last attempt, the prompt
        itself withholds the correct detail in favor of one clue and
        a retry invitation -- `needs_retry` is the routing signal
        voice_loop_demo.py uses to decide whether to capture one more
        attempt, bounded to exactly one retry (max_attempts=2 by
        default). Screened like any other spoken output in this class;
        if the screened text is blocked, needs_retry is forced False
        -- never retry into an unsafe-reply loop, just move on with
        the safe decline message."""
        prompt = build_reaction_prompt(
            story_text, question, child_answer, age,
            attempt_number=attempt_number, max_attempts=max_attempts,
        )
        reply_text, _model = await self._llm.generate_reply(
            [{"role": "user", "content": "React now."}], prompt
        )
        reaction = parse_comprehension_reaction(reply_text, child_answer)
        # Decision 0083, found live: the model rejected "red" for
        # "What color is Dan's dog?" against a story that says "Dan
        # has a red dog" -- then admitted on the final attempt it was
        # right all along. A literal word match against the story
        # text is a cheap, deterministic reason not to trust a
        # "needs_retry" verdict; the model's own SAY text is skipped
        # too, since it was written assuming the answer was wrong.
        #
        # Decision 0097, found live: a different shape of the same
        # failure -- the model marked it "resolved" (so no retry was
        # asked for) but its own SAY text still read like an
        # unresolved clue ("...but think about what that something
        # was again!") for an answer ("Log.") that literally matches
        # the story ("A hen sat on a log."). Same override, triggered
        # either by the model's own needs_retry verdict OR by its
        # text still sounding like a retry invitation despite saying
        # resolved -- either way, a literal match means the answer
        # shouldn't be second-guessed.
        if answer_matches_story_text(child_answer, story_text) and (
            reaction.needs_retry or sounds_like_a_retry_invitation(reaction.text)
        ):
            reaction = ComprehensionReaction(text=LITERAL_MATCH_AFFIRMATION, needs_retry=False)
        screened = self._screen(reaction.text)
        if screened.blocked:
            return ComprehensionReaction(text=screened.text, needs_retry=False)
        return ComprehensionReaction(text=screened.text, needs_retry=reaction.needs_retry)

    async def react_to_word_game_answer(
        self, story_text: str, results: list[tuple[str, bool]], age: int | None = None
    ) -> ConversationResult:
        """Decision 0112: ONE warm, combined reaction to every missing
        word in the "missing letters" bonus game, replacing the old
        fixed 3-line "correct" pool / single incorrect template --
        found live, those never actually engaged with what the child
        said at all. `results` ([(word, was_correct), ...]) is already
        decided deterministically (word_game.is_correct_answer()) --
        the model's job is phrasing one combined reply, not judging
        correctness. Screened like every other spoken output in this
        class."""
        prompt = build_word_game_reaction_prompt(story_text, results, age)
        reply_text, _model = await self._llm.generate_reply(
            [{"role": "user", "content": "React now."}], prompt
        )
        return self._screen(reply_text)

    async def generate_word_family(
        self, word: str, mastered_levels: list[str], age: int | None = None, num_words: int = 4
    ) -> list[str]:
        """Decision 0066: once a word is read successfully, a small
        set of same-pattern words (mat -> cat, sat, bat, rat) to check
        the skill generalized, not just that one word. The LLM
        proposes candidates; each is independently verified against
        word_family.verify_family_word() (exact rime match + decodable
        at the child's current level) and a failing candidate is
        simply dropped, not retried -- same screen-and-drop shape as
        generate_comprehension_questions(), since there's no single
        "fix" for a bad rhyme. Returns [] if `word` has only one
        grapheme (nothing to vary) or if every candidate fails
        verification -- the caller skips the activity gracefully.

        Decision 0113, found live: asking for exactly `num_words`
        candidates routinely delivered fewer -- the verifier's three
        checks (real word, exact rime, decodable) are strict enough
        that losing half of 4 requested candidates to a miss on any
        one of them is common, and nothing backfilled the gap. Asking
        the LLM for more than `num_words` up front (still one call,
        no retry round-trip) absorbs that drop rate; the result is
        still capped to `num_words` below, same as before."""
        rime = extract_rime(word)
        if rime is None:
            return []
        rime_spelling, rime_graphemes = rime
        prompt = build_family_prompt(word, rime_spelling, num_words * _FAMILY_OVERREQUEST_FACTOR)
        reply_text, _model = await self._llm.generate_reply(
            [{"role": "user", "content": "Write the words now."}], prompt
        )
        candidates = parse_family_words(reply_text)
        verified = [
            candidate
            for candidate in candidates
            if candidate.strip().lower() != word.strip().lower()
            and verify_family_word(candidate, rime_graphemes, mastered_levels)
        ]
        safe_words = [w for w in verified if check_speech(w).allowed]
        return safe_words[:num_words]

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
