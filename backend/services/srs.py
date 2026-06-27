"""
Simplified SM-2 spaced-repetition scheduler.

Flashcard reviews in this app are graded on a binary scale (1 = again/fail,
4 = got it/pass) rather than SM-2's original 0-5 quality scale. This collapses
SM-2's quality-dependent ease adjustment into a fixed step per outcome —
fail resets repetitions and shortens the interval; pass grows it.
"""
from datetime import datetime, timedelta, timezone

MIN_EASE     = 1.3
MAX_EASE     = 2.8
DEFAULT_EASE = 2.5


def next_state(
    rating: int,
    repetitions: int,
    ease_factor: float,
    interval_days: float,
) -> tuple[int, float, float, datetime]:
    """
    rating: 1 (again/fail) treated as fail; any other value (2-4) as pass.
    Returns (new_repetitions, new_ease_factor, new_interval_days, due_at).
    """
    if rating <= 1:
        repetitions   = 0
        ease_factor   = max(MIN_EASE, ease_factor - 0.2)
        interval_days = 1.0
    else:
        repetitions  += 1
        ease_factor   = min(MAX_EASE, ease_factor + 0.1)
        if repetitions == 1:
            interval_days = 1.0
        elif repetitions == 2:
            interval_days = 6.0
        else:
            interval_days = round(interval_days * ease_factor, 1)

    due_at = datetime.now(timezone.utc) + timedelta(days=interval_days)
    return repetitions, ease_factor, interval_days, due_at
