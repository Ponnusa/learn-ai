"""Reading Partner v2's deterministic state machine (decision 0075).

A second, parallel reading flow, built from a product-owner critique
of the original (decisions 0051-0074): model the sentence first,
read it together, let the child try independently, practice only the
words that turn out to actually be hard (capped at two), then check
understanding -- with a child who reads well on the first try praised
and moved on immediately, never forced through the full sequence.

Deliberately separate from, and never imported by, the original
Reading Partner (voice_loop_demo._run_reading_partner) -- the whole
point, per explicit instruction, is a new version that can be
switched to and back from at any time without touching the old one.
See voice_loop_demo._run_reading_partner_v2() for the real I/O
(speaking, listening, rendering); everything here is pure and
I/O-free, so the state transitions themselves are fully unit-testable
without a single fake microphone.

The critique's own central design point: "make this a deterministic
state machine rather than letting the LLM decide what happens next."
The LLM (via ConversationService) only ever phrases comprehension
questions and reactions here -- it never decides which state comes
next or whether an answer counts as correct.
"""
from dataclasses import dataclass, field
from enum import Enum

from .alignment import assess
from .hints import pick_hint_words
from .schema import AssessmentResult


class ReadingState(str, Enum):
    INTRO = "intro"
    INDEPENDENT_READ = "independent_read"
    MODEL_READ = "model_read"
    READ_TOGETHER = "read_together"
    SECOND_INDEPENDENT_READ = "second_independent_read"
    WORD_PRACTICE = "word_practice"
    FINAL_REREAD = "final_reread"
    COMPREHENSION = "comprehension"
    COMPLETE = "complete"


# A first independent read at or above this accuracy skips straight
# to comprehension -- "if the child reads it well on the first
# attempt, praise them, check understanding, and finish" (the
# critique's own adaptive rule). Same accuracy banding feedback.py
# already uses for its own "really well" praise -- not re-exported
# from there since feedback.py never named it as a constant, but
# intentionally the same number, not a coincidence.
CLEAN_READ_ACCURACY = 0.95

# "Let's practise just two tricky words together" -- the critique's
# own cap, matching feedback.py's _MAX_PRACTICE_WORDS/hints.py's
# _MAX_HINT_WORDS in spirit (a small, named, deliberate limit) without
# literally importing either, since v2's reasons for the cap (keep one
# sentence's session short) aren't the same reasons v1's are.
MAX_PRACTICE_WORDS = 2


@dataclass
class SentenceSession:
    """Everything the state machine needs to decide what happens next
    for ONE sentence: the target text, the current state, every
    assessed attempt so far (in order), and which words are still
    candidates for targeted practice. One instance per sentence --
    voice_loop_demo._run_reading_partner_v2() creates a fresh one for
    each sentence in the passage."""

    sentence: str
    sight_words: set[str] = field(default_factory=set)
    state: ReadingState = ReadingState.INTRO
    attempts: list[AssessmentResult] = field(default_factory=list)
    practice_words: list[str] = field(default_factory=list)

    def record_attempt(self, spoken: str, duration_seconds: float) -> AssessmentResult:
        """Grades one read-aloud attempt against this sentence and
        remembers it -- every attempt is recorded for the session's
        own history, regardless of whether the caller goes on to use
        its evidence for mastery or word-practice selection."""
        result = assess(
            self.sentence, spoken, duration_seconds=duration_seconds, sight_words=self.sight_words
        )
        self.attempts.append(result)
        return result

    def decide_after_first_read(self, result: AssessmentResult) -> ReadingState:
        """A clean first attempt (decoding, not comprehension) skips
        straight to checking understanding -- "don't make the child
        repeat the entire sentence too many times" was an explicit
        complaint about the naive always-practice version. Anything
        less than clean starts the supported model -> together ->
        second-independent sequence."""
        self.state = (
            ReadingState.COMPREHENSION
            if result.accuracy >= CLEAN_READ_ACCURACY
            else ReadingState.MODEL_READ
        )
        return self.state

    def decide_after_second_read(self, result: AssessmentResult) -> ReadingState:
        """After the supported second attempt, pick up to
        MAX_PRACTICE_WORDS real misses worth practicing (reusing
        hints.py's own is_worth_practicing() bar via pick_hint_words()
        -- the same deterministic miscue-detection the original
        Reading Partner already relies on; this is a different FLOW
        around the same proven grading core, not a second grading
        algorithm). No real misses -> straight to comprehension."""
        self.practice_words = pick_hint_words(result, max_words=MAX_PRACTICE_WORDS)
        self.state = (
            ReadingState.WORD_PRACTICE if self.practice_words else ReadingState.COMPREHENSION
        )
        return self.state

    def finish_word_practice(self) -> ReadingState:
        self.state = ReadingState.FINAL_REREAD
        return self.state

    def finish_final_reread(self) -> ReadingState:
        self.state = ReadingState.COMPREHENSION
        return self.state

    def complete(self) -> ReadingState:
        self.state = ReadingState.COMPLETE
        return self.state


# Deterministic, fixed-phrase checks for two things an LLM must not be
# trusted to silently decide on its own (per the critique's own
# "the LLM must not silently switch the target" instruction): whether
# the child is asking for help outright (so an empty/near-empty first
# attempt isn't graded as a bad read) and whether the child wants to
# stop (so the session ends warmly instead of pushing through a
# frustrated child). Small, fixed lists rather than an LLM classifier
# -- same "deterministic over LLM wherever possible" discipline this
# whole package follows ([[feedback_deterministic_over_llm]]).
_HELP_REQUEST_PHRASES = (
    "read with me", "help me", "help", "i dont know", "i don't know", "not sure",
)
_STOP_REQUEST_PHRASES = (
    "stop", "i dont want to", "i don't want to", "this is too hard", "im done", "i'm done",
    "i want to stop", "no more",
)


def seems_like_a_help_request(text: str) -> bool:
    """True if `text` reads as the child asking for help rather than
    attempting the sentence -- e.g. a near-empty capture, or an
    explicit ask. Checked BEFORE grading a first attempt, so a child
    who said nothing/asked for help isn't told their "reading" was
    inaccurate."""
    cleaned = text.strip().lower()
    if not cleaned:
        return True
    return any(phrase in cleaned for phrase in _HELP_REQUEST_PHRASES)


def seems_like_a_stop_request(text: str) -> bool:
    """True if `text` reads as the child wanting to stop the exercise
    -- checked after any capture during the supported/practice
    sequence, so a frustrated child is never pushed through the rest
    of the flow. The critique's own explicit rule: "if the child is
    becoming frustrated, stop on a positive note and save where they
    need help" -- deterministic, not an LLM's judgment call."""
    cleaned = text.strip().lower()
    return any(phrase in cleaned for phrase in _STOP_REQUEST_PHRASES)
