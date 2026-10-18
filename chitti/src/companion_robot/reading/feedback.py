"""Deterministic spoken feedback for a Reading Partner turn (decision
0051) -- no LLM call, by design, same "deterministic over LLM"
instinct education/math_check.py's build_math_check_note() already
follows for math -- except this is spoken directly to the child rather
than fed to a model as a note, since there's no free-form conversation
happening here to weave it into. Never raw accuracy percentages or
WCPM numbers dumped on a child -- qualitative, warm framing only.
"""
from .schema import AssessmentResult, MasteryDelta


_MAX_SPOKEN_SOUNDS = 3


def build_reading_feedback(assessment: AssessmentResult, delta: MasteryDelta) -> str:
    if assessment.accuracy >= 0.95:
        parts = ["Wow, you read that really well!"]
    elif assessment.accuracy >= 0.75:
        parts = ["Nice reading! You got most of it."]
    else:
        parts = ["Good try! Reading can be tricky sometimes."]

    # Found live: a near-perfect first read can cross the mastery
    # threshold for a dozen-plus graphemes in one session, and
    # mastery.py's grapheme_evidence keys aren't all speakable --
    # alignment.py also tracks internal, non-phonemic sentinels like
    # "_blend_" (any adjacent consonant blend) and "-s"/"-ed" (suffix
    # endings) for the BKT model's own bookkeeping, never meant to be
    # read aloud as if they were letter-sounds. A real grapheme key is
    # always plain letters (e.g. "sh", "ee") -- isalpha() is enough to
    # tell the two apart without hardcoding every sentinel name.
    speakable = [g for g in delta.newly_mastered if g.isalpha()]
    if speakable:
        sounds = _spoken_list(speakable)
        plural = "s" if len(speakable) > 1 else ""
        parts.append(f"You're getting really good at the {sounds} sound{plural}!")

    return " ".join(parts)


def _spoken_list(items: list[str], max_items: int = _MAX_SPOKEN_SOUNDS) -> str:
    """Caps how many sounds are named in one breath -- naming a dozen-
    plus in a single sentence (found live) doesn't read as praise, it
    reads as an overwhelming list."""
    shown = items[:max_items]
    quoted = [f"'{item}'" for item in shown]
    if len(items) > max_items:
        return ", ".join(quoted) + ", and more"
    if len(quoted) == 1:
        return quoted[0]
    return ", ".join(quoted[:-1]) + " and " + quoted[-1]
