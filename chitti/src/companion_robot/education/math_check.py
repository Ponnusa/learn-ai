"""Deterministic addition-fact checking (decision 0024) -- the one
corner of the Education Engine's original "engine owns correctness"
principle (spec section 7) that's actually cheap to build: a + b has
one real answer, unlike grammar or pronunciation. No LLM involved in
deciding whether a claimed sum is correct -- only in how the verified
result gets phrased back to the child (see conversation/prompts.py's
build_math_check_note()).

extract_addition_claim() covers a complete claim stated in one
utterance ("one plus one is two", "2+2=5") -- the "child teaches
Chitti a math fact" case.

extract_posed_challenge()/extract_bare_number() (decision 0025) cover
the other, more common real-world case: *Chitti* poses a challenge in
its own free-form reply ("if you have 2 chocolates and get 3 more...")
and the child answers with just a number next turn. voice_loop_demo.py
retroactively recognizes the posed challenge from Chitti's own text
(best-effort -- free-form narrative, not a fixed phrasing) and
remembers it for exactly one turn so the child's bare-number reply can
still be verified deterministically.

Multi-word numbers ("twenty two") aren't recognized by any of these.
All of this returns None on anything unrecognized rather than
guessing -- accepted gaps, not silent wrong guesses.
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

_NUMBER_TOKEN = r"(?:\d+|" + "|".join(_WORD_NUMBERS) + r")"

# Loose on purpose: Chitti poses challenges in free-form narrative
# ("2 chocolates and 3 more", "2 treats plus 3 berries makes..."), not
# a fixed phrasing. Restricting a/b to actual number tokens (not any
# \w+) avoids matching a non-number word in between ("chocolates") as
# though it were the second operand. Still best-effort -- may
# occasionally miss unusual wording or pick up an unrelated pair of
# numbers; low-stakes since the only consequence is one odd follow-up
# note, not a safety issue.
_PLUS_CHALLENGE_PATTERN = re.compile(
    rf"\b(?P<a>{_NUMBER_TOKEN})\b(?:(?!\.).){{0,20}}?(?:\+|plus)(?:(?!\.).){{0,20}}?"
    rf"\b(?P<b>{_NUMBER_TOKEN})\b",
    re.IGNORECASE,
)
_MORE_CHALLENGE_PATTERN = re.compile(
    rf"\b(?P<a>{_NUMBER_TOKEN})\b(?:(?!\.).){{0,40}}?\b(?P<b>{_NUMBER_TOKEN})\b"
    rf"(?:(?!\.).){{0,15}}?\bmore\b",
    re.IGNORECASE,
)

_BARE_NUMBER_PATTERN = re.compile(rf"\b{_NUMBER_TOKEN}\b", re.IGNORECASE)


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


def build_result(a: int, b: int, claimed_sum: int) -> MathCheckResult:
    correct_sum = a + b
    return MathCheckResult(
        a=a, b=b, claimed_sum=claimed_sum, correct_sum=correct_sum, correct=claimed_sum == correct_sum
    )


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
    return build_result(a, b, claimed_sum)


def extract_posed_challenge(text: str) -> tuple[int, int] | None:
    """Recognizes Chitti's own reply posing an addition challenge
    ("2 chocolates and 3 more", "2 treats plus 3 berries makes...").
    Tries the "plus"/"+" shape first, then the "N more" shape, each
    confined to one sentence (never crosses a '.'). Returns the two
    operands, or None if nothing recognizable is found -- the caller
    then just has no pending challenge to check next turn, same as
    today's behavior."""
    for pattern in (_PLUS_CHALLENGE_PATTERN, _MORE_CHALLENGE_PATTERN):
        match = pattern.search(text)
        if not match:
            continue
        a, b = _to_int(match["a"]), _to_int(match["b"])
        if a is not None and b is not None:
            return (a, b)
    return None


def extract_bare_number(text: str) -> int | None:
    """The LAST standalone number (digit or word) in a reply -- not
    the first, since counting out loud ("1, 2, 3, 4, 5.") should
    resolve to the final tally, not the first number said."""
    matches = _BARE_NUMBER_PATTERN.findall(text)
    if not matches:
        return None
    return _to_int(matches[-1])
