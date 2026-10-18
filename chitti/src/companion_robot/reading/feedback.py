"""Deterministic spoken feedback for a Reading Partner turn (decision
0051) -- no LLM call, by design, same "deterministic over LLM"
instinct education/math_check.py's build_math_check_note() already
follows for math -- except this is spoken directly to the child rather
than fed to a model as a note, since there's no free-form conversation
happening here to weave it into. Never raw accuracy percentages or
WCPM numbers dumped on a child -- qualitative, warm framing only.
"""
from .schema import AssessmentResult, MasteryDelta


def build_reading_feedback(assessment: AssessmentResult, delta: MasteryDelta) -> str:
    if assessment.accuracy >= 0.95:
        parts = ["Wow, you read that really well!"]
    elif assessment.accuracy >= 0.75:
        parts = ["Nice reading! You got most of it."]
    else:
        parts = ["Good try! Reading can be tricky sometimes."]

    if delta.newly_mastered:
        sounds = _spoken_list(delta.newly_mastered)
        plural = "s" if len(delta.newly_mastered) > 1 else ""
        parts.append(f"You're getting really good at the {sounds} sound{plural}!")

    return " ".join(parts)


def _spoken_list(items: list[str]) -> str:
    quoted = [f"'{item}'" for item in items]
    if len(quoted) == 1:
        return quoted[0]
    return ", ".join(quoted[:-1]) + " and " + quoted[-1]
