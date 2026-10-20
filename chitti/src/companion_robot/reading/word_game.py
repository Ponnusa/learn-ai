"""Post-reading "missing letters" bonus game (decision 0057) -- a fun,
deterministic engagement activity after a book's feedback, not part
of the decoding-mastery assessment pipeline. No LLM call, no scoring
persisted -- reading/mastery.py and reading/alignment.py are
untouched by this module.

"Japan" -> "J_P_N": blanks every vowel-kind grapheme, keeps every
consonant visible. Reuses decodability.decompose()'s existing per-
letter vowel/consonant tagging rather than inventing new segmentation
logic, so a vowel team (e.g. "boat"'s "oa") blanks as one unit, the
phonics-correct granularity for this curriculum.
"""
import random

from .alignment import tokenize
from .decodability import clean_word, decompose
from .hints import blend_breakdown

_MIN_WORD_LENGTH = 3
_MAX_WORDS = 2

_CORRECT_RESPONSES = [
    "Yes! That's exactly it!",
    "You got it!",
    "That's right, nice work!",
]

# Decision 0070: found live -- a wrong guess (e.g. "frog" blanked to
# "fr_g", child says just the letter "o") got nothing but the answer
# handed over, no phonics explanation at all, unlike the hint ladder's
# own graduated breakdown (decision 0064). Reusing hints.py's
# blend_breakdown() here gives this fun bonus game the same
# phoneme-accurate teaching moment on a miss, without turning it into
# a second, duplicate hint ladder -- still one line, still moves on
# right after.
_INCORRECT_TEMPLATE = (
    'Good try! The word is "{word}" -- {breakdown}. Let\'s keep going!'
)

_CLOSING_LINES = [
    "You're a word wizard! That was so much fun.",
    "Wow, your word-detective skills are amazing!",
    "That was a blast -- let's do it again sometime!",
]


def pick_game_words(words: list[str], max_words: int = _MAX_WORDS) -> list[str]:
    """Picks up to `max_words` distinct, substantial words from a
    book's text to play the game with -- the longest qualifying
    words, since a longer word makes a more interesting puzzle. Skips
    anything shorter than _MIN_WORD_LENGTH or with no vowel-kind
    grapheme to blank at all."""
    seen: set[str] = set()
    candidates: list[str] = []
    for raw in words:
        word = clean_word(raw)
        if not word or len(word) < _MIN_WORD_LENGTH or word in seen:
            continue
        if not any(g.kind == "V" for g in decompose(word).graphemes):
            continue
        seen.add(word)
        candidates.append(word)
    candidates.sort(key=len, reverse=True)
    return candidates[:max_words]


def blank_vowels(word: str) -> str:
    """"japan" -> "j_p_n" -- blanks the character span of every vowel-
    kind grapheme, leaves consonant-kind spans untouched."""
    chars = list(word)
    for grapheme in decompose(word).graphemes:
        if grapheme.kind == "V":
            start, end = grapheme.span
            for i in range(start, end):
                chars[i] = "_"
    return "".join(chars)


def spell_out_blanked(blanked: str) -> str:
    """"j_p_n" -> "J, blank, P, blank, N" -- a speakable version for
    TTS, since underscores mean nothing read aloud."""
    parts = [ch.upper() if ch != "_" else "blank" for ch in blanked]
    return ", ".join(parts)


def is_correct_answer(word: str, spoken: str) -> bool:
    """Lenient on purpose: true if the target word appears anywhere in
    the child's reply, so a child who spells the missing letters out
    first and then says the whole word still gets credit -- the same
    "don't penalize extra talk" spirit reading/hints.py's own matching
    already follows."""
    return clean_word(word) in tokenize(spoken)


def random_correct_response() -> str:
    return random.choice(_CORRECT_RESPONSES)


def incorrect_response(word: str) -> str:
    return _INCORRECT_TEMPLATE.format(word=word, breakdown=blend_breakdown(word))


def random_closing_line() -> str:
    return random.choice(_CLOSING_LINES)
