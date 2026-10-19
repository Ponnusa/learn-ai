"""Graduated hint ladder for a struggling word (decision 0052) -- no
LLM call, by design, same instinct as feedback.py.

Deliberately post-hoc, not live: Chitti's audio capture
(voice_loop_demo._capture_and_transcribe) is push-to-talk -- record
until Enter, then transcribe once. There's no streaming/partial
transcription or voice-activity detection, so there's no way to notice
a child pausing mid-sentence and jump in. The feasible shape is: let
the child finish the whole passage, grade it, then -- if grading
surfaced a real miss -- offer a short hint-and-retry exchange for that
one word before the normal feedback. One hint-word per book in V1.
"""
from .alignment import OMISSION, SUBSTITUTION
from .curriculum import DEFAULT_SIGHT_WORDS
from .decodability import clean_word, decompose
from .schema import AssessmentResult

_HINT_STAGES = 3

# Found live: a 1-2 letter word like "a" or "I" got selected as a hint
# target -- "that word starts with the 'a' sound" is nonsensical for a
# word that IS the sound, nothing to graduate into sounding out. 3
# letters is deliberately the level this curriculum's own shortest
# real phonics targets sit at (CVC words like "cat"/"sat"/"mat") --
# short enough to keep those, long enough to skip trivial function words.
_MIN_HINT_WORD_LENGTH = 3

# Decision 0058, also found live: "the" passed the length check above
# but is a sight word (curriculum.DEFAULT_SIGHT_WORDS) -- meant to be
# recognized by memory, not sounded out. "Let's sound it out: th-e"
# doesn't apply to it, and the child's actual reply ("Duh!") read as
# genuine annoyance at being asked to sound out something that trivial.
_SIGHT_WORDS = {clean_word(w) for w in DEFAULT_SIGHT_WORDS}


def is_worth_practicing(word: str) -> bool:
    """True if `word` is substantial enough to practice -- not
    trivially short, not a sight word (meant to be recognized by
    memory, not decoded). Shared by pick_hint_word() and
    feedback.py's own practice-word list (decision 0060), so both
    apply exactly the same bar for "a real word worth calling out,"
    not two definitions that can drift apart."""
    return len(word) >= _MIN_HINT_WORD_LENGTH and clean_word(word) not in _SIGHT_WORDS


def pick_hint_word(assessment: AssessmentResult) -> str | None:
    """Returns the first real-error word (substitution/omission) worth
    a graduated hint, or None if there isn't one. self_correction/
    hesitation/insertion miscues are skipped -- assess() itself
    already treats those as not the child's fault. Words that aren't
    is_worth_practicing() are skipped too -- the search continues to
    the next real miscue rather than giving up outright."""
    for miscue in assessment.miscues:
        if (
            miscue.kind in (SUBSTITUTION, OMISSION)
            and miscue.expected
            and is_worth_practicing(miscue.expected)
        ):
            return miscue.expected
    return None


def build_hint_line(word: str, stage: int) -> str:
    """stage 0: encourage + sound-it-out. stage 1: first-sound hint.
    stage 2: say the word and invite one more try. Mirrors the source
    product's own graduated-hint content, applied after the read
    instead of during it."""
    if stage == 0:
        return "Let's try that word again -- take your time and sound it out."
    if stage == 1:
        first_sound = _first_sound(word)
        return f"Here's a hint: that word starts with the '{first_sound}' sound."
    return f'That word is "{word}" -- can you say it back to me?'


def _first_sound(word: str) -> str:
    graphemes = decompose(word).graphemes
    return graphemes[0].grapheme if graphemes else word[0]
