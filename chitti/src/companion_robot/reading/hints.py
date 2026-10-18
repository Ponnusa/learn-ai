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
from .decodability import decompose
from .schema import AssessmentResult

_HINT_STAGES = 3


def pick_hint_word(assessment: AssessmentResult) -> str | None:
    """Returns the first real-error word (substitution/omission) worth
    a graduated hint, or None on a clean read. self_correction/
    hesitation/insertion miscues are skipped -- assess() itself
    already treats those as not the child's fault."""
    for miscue in assessment.miscues:
        if miscue.kind in (SUBSTITUTION, OMISSION) and miscue.expected:
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
