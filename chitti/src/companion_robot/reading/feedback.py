"""Deterministic spoken feedback for a Reading Partner turn (decision
0051) -- no LLM call, by design, same "deterministic over LLM"
instinct education/math_check.py's build_math_check_note() already
follows for math -- except this is spoken directly to the child rather
than fed to a model as a note, since there's no free-form conversation
happening here to weave it into. Never raw accuracy percentages or
WCPM numbers dumped on a child -- qualitative, warm framing only.

Decision 0060: found live -- the hint-and-retry loop (decision 0052)
only ever addresses ONE word per book, so a session with more than one
real miss left every other missed word completely unmentioned; the
final feedback either praised an unrelated word or said nothing
actionable at all, despite the product owner's explicit ask ("give
some words for him to practice"). build_reading_feedback() now always
surfaces the real missed words from THIS read (not just whichever one
the hint ladder happened to pick), using the same is_worth_practicing()
bar hints.py already established, so a resolved hint word doesn't get
redundantly re-mentioned but anything else missed does.
"""
from .alignment import OMISSION, SUBSTITUTION
from .decodability import clean_word
from .hints import is_worth_practicing
from .schema import AssessmentResult, MasteryDelta

_STANDOUT_MIN_LENGTH = 4
_MAX_PRACTICE_WORDS = 3


def build_reading_feedback(
    assessment: AssessmentResult, delta: MasteryDelta, resolved_word: str | None = None
) -> str:
    """`resolved_word` is the word the hint-and-retry loop (decision
    0052) worked on, passed only if the child *did* get it right by
    the end -- excluded from the practice-words list below so it's
    never redundantly re-mentioned moments after being fixed live.
    Pass None (the default) when there was no hint this turn, or it
    was never resolved -- in that case it surfaces naturally, since
    it's still a real miscue in `assessment`."""
    if assessment.accuracy >= 0.95:
        parts = ["Wow, you read that really well!"]
    elif assessment.accuracy >= 0.75:
        parts = ["Nice reading! You got most of it."]
    else:
        parts = ["Good try! Reading can be tricky sometimes."]

    practice_words = _practice_words(assessment, exclude=resolved_word)
    if practice_words:
        parts.append(_practice_sentence(practice_words))
    else:
        standout = _standout_word(assessment.correct_words)
        if standout:
            parts.append(f'I especially loved how you read "{standout}"!')

    return " ".join(parts)


def _practice_words(assessment: AssessmentResult, exclude: str | None = None) -> list[str]:
    """Every real missed word from this read worth practicing (same
    is_worth_practicing() bar hints.py's pick_hint_word() uses),
    deduped, in reading order, capped at _MAX_PRACTICE_WORDS -- not
    just the single word the hint ladder happened to address."""
    excluded = clean_word(exclude) if exclude else None
    seen: set[str] = set()
    words: list[str] = []
    for miscue in assessment.miscues:
        if miscue.kind not in (SUBSTITUTION, OMISSION) or not miscue.expected:
            continue
        if not is_worth_practicing(miscue.expected):
            continue
        cleaned = clean_word(miscue.expected)
        if cleaned == excluded or cleaned in seen:
            continue
        seen.add(cleaned)
        words.append(miscue.expected)
        if len(words) >= _MAX_PRACTICE_WORDS:
            break
    return words


def _practice_sentence(words: list[str]) -> str:
    quoted = [f'"{w}"' for w in words]
    joined = quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " and " + quoted[-1]
    plural = "s" if len(quoted) > 1 else ""
    return f"Let's practice the word{plural} {joined} next time!"


def _standout_word(correct_words: list[str], min_length: int = _STANDOUT_MIN_LENGTH) -> str | None:
    """Picks a specific, real word the child actually read correctly
    -- concrete evidence, not a generic sound label. The longest word
    at least `min_length` letters, since a short, common word ("a",
    "is") isn't a notable callout. Only used when there's nothing to
    practice -- a clean read still gets something specific, not just
    a generic "well done.\""""
    candidates = [w for w in correct_words if len(w) >= min_length]
    if not candidates:
        return None
    return max(candidates, key=len)
