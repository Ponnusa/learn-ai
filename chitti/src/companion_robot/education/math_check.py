"""Deterministic addition-fact checking (decision 0024) -- the one
corner of the Education Engine's original "engine owns correctness"
principle (spec section 7) that's actually cheap to build: a + b has
one real answer, unlike grammar or pronunciation. No LLM involved in
deciding whether a claimed sum is correct -- only in how the verified
result gets phrased back to the child (see conversation/prompts.py's
build_math_check_note()).

Scope: only a complete claim stated in one utterance ("one plus one
is two", "2+2=5"), covering the "child teaches Chitti a math fact"
case. A bare reply to a question Chitti itself posed (just "five.",
no restated operands) isn't covered -- that needs app-owned,
cross-turn challenge-number tracking, out of scope for this check.
Multi-word numbers ("twenty two") aren't recognized either; both are
accepted gaps, not silent wrong guesses -- unrecognized text simply
returns None and the turn proceeds as an ordinary conversation.
"""
import re
from dataclasses import dataclass

_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

_CLAIM_PATTERN = re.compile(
    r"(?P<a>\w+)\s*(?:\+|plus)\s*(?P<b>\w+)\s*(?:=|is|equals|makes)\s*(?P<c>\w+)",
    re.IGNORECASE,
)


@dataclass
class MathCheckResult:
    a: int
    b: int
    claimed_sum: int
    correct_sum: int
    correct: bool


def _to_int(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


def extract_addition_claim(text: str) -> MathCheckResult | None:
    match = _CLAIM_PATTERN.search(text)
    if not match:
        return None
    a, b, claimed_sum = (_to_int(match[g]) for g in ("a", "b", "c"))
    if a is None or b is None or claimed_sum is None:
        return None
    # A multi-word number like "twenty two" would otherwise silently
    # mis-match on just its last word ("two") -- checking the token
    # immediately before `a` and immediately after `c` catches that
    # compound and returns None rather than guessing wrong.
    before = text[: match.start("a")].rstrip().split()
    after = text[match.end("c") :].lstrip().split()
    if (before and before[-1].lower() in _WORD_NUMBERS) or (
        after and after[0].lower() in _WORD_NUMBERS
    ):
        return None
    correct_sum = a + b
    return MathCheckResult(
        a=a, b=b, claimed_sum=claimed_sum, correct_sum=correct_sum, correct=claimed_sum == correct_sum
    )
