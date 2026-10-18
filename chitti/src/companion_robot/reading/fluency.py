"""Fluency metrics (decision 0051) -- ported from phono-storyforge's
app/skills/fluency.py (Apache 2.0). Two tiny pure functions so
alignment.py computes them the same way every time. Self-corrections
and hesitations are not errors -- the caller passes the count of words
ultimately read correctly, so those are already folded in.
"""


def accuracy(words_correct: int, total_words: int) -> float:
    """Fraction of expected words read correctly (1.0 for an empty passage)."""
    if total_words <= 0:
        return 1.0
    return words_correct / total_words


def wcpm(words_correct: int, duration_seconds: float) -> float:
    """Words Correct Per Minute. 0.0 when no time elapsed."""
    if duration_seconds <= 0:
        return 0.0
    return words_correct * 60.0 / duration_seconds
