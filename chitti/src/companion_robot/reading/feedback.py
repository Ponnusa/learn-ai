"""Deterministic spoken feedback for a Reading Partner turn (decision
0051) -- no LLM call, by design, same "deterministic over LLM"
instinct education/math_check.py's build_math_check_note() already
follows for math -- except this is spoken directly to the child rather
than fed to a model as a note, since there's no free-form conversation
happening here to weave it into. Never raw accuracy percentages or
WCPM numbers dumped on a child -- qualitative, warm framing only.

Decision 0055: replaces the original per-book mastery-sound
announcement (decision 0051, capped but not removed by decision
0054) with evidence tied to this specific read -- a real word the
child actually said correctly, or the one word still worth practicing
-- found live to read as more genuine than a list of phonics sound
labels disconnected from what was actually read, and to avoid
implying broad mastery from a single read. Mastery itself is
unaffected -- reading/mastery.py still updates and persists it every
turn; it's just no longer announced after every single book.
"""
from .schema import AssessmentResult, MasteryDelta

_STANDOUT_MIN_LENGTH = 4


def build_reading_feedback(
    assessment: AssessmentResult, delta: MasteryDelta, hint_word: str | None = None
) -> str:
    """`hint_word` is the word the hint-and-retry loop (decision 0052)
    worked on, passed only if the child never got it right -- gives
    one gentle, specific thing to revisit next time instead of ending
    on an unresolved struggle. Pass None (the default) when there was
    no hint this turn, or the child got it right."""
    if assessment.accuracy >= 0.95:
        parts = ["Wow, you read that really well!"]
    elif assessment.accuracy >= 0.75:
        parts = ["Nice reading! You got most of it."]
    else:
        parts = ["Good try! Reading can be tricky sometimes."]

    if hint_word:
        parts.append(f'Let\'s keep practicing the word "{hint_word}" together next time.')
    else:
        standout = _standout_word(assessment.correct_words)
        if standout:
            parts.append(f'I especially loved how you read "{standout}"!')

    return " ".join(parts)


def _standout_word(correct_words: list[str], min_length: int = _STANDOUT_MIN_LENGTH) -> str | None:
    """Picks a specific, real word the child actually read correctly
    -- concrete evidence, not a generic sound label. The longest word
    at least `min_length` letters, since a short, common word ("a",
    "is") isn't a notable callout."""
    candidates = [w for w in correct_words if len(w) >= min_length]
    if not candidates:
        return None
    return max(candidates, key=len)
