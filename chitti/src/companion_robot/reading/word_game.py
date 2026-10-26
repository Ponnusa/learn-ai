"""Post-reading "missing letters" bonus game (decision 0057) -- a fun
engagement activity after a book's feedback, not part of the decoding-
mastery assessment pipeline. No scoring persisted -- reading/mastery.py
and reading/alignment.py are untouched by this module. Decision 0112
added one real LLM call (see build_word_game_reaction_prompt() below)
for the combined correct/incorrect reaction -- which words were right
or wrong is still decided deterministically by is_correct_answer()
below, never left to the model; the LLM's only job is phrasing one
warm, combined reaction, not grading.

"Japan" -> "J_p_n": blanks every vowel-kind grapheme, keeps every
consonant visible, in the word's own original casing (decision 0112 --
found live, blanking an already-lowercased copy lost a story word's
real capitalization, e.g. "Sam" -> "s_m" instead of "S_m"). Reuses
decodability.decompose()'s existing per-letter vowel/consonant tagging
rather than inventing new segmentation logic, so a vowel team (e.g.
"boat"'s "oa") blanks as one unit, the phonics-correct granularity for
this curriculum.
"""
import random

from .alignment import tokenize
from .decodability import clean_word, decompose
from .hints import blend_breakdown

_MIN_WORD_LENGTH = 3
_MAX_WORDS = 2

_CLOSING_LINES = [
    "You're a word wizard! That was so much fun.",
    "Wow, your word-detective skills are amazing!",
    "That was a blast -- let's do it again sometime!",
]

# Decision 0070: found live -- a wrong guess (e.g. "frog" blanked to
# "fr_g", child says just the letter "o") got nothing but the answer
# handed over, no phonics explanation at all, unlike the hint ladder's
# own graduated breakdown (decision 0064). Reusing hints.py's
# blend_breakdown() here gives a wrong guess the same phoneme-accurate
# teaching moment, without turning it into a second, duplicate hint
# ladder -- still one line, still moves on right after. Decision 0112
# kept this deterministic template for voice_loop_demo.py's own
# word-FAMILY practice mode (_run_word_family_practice(), a different
# feature) -- this missing-letters game's own reaction is now the LLM
# call above instead.
_INCORRECT_TEMPLATE = (
    'Good try! The word is "{word}" -- {breakdown}. Let\'s keep going!'
)


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
    """"Japan" -> "J_p_n" -- blanks the character span of every vowel-
    kind grapheme, leaves consonant-kind spans untouched, in `word`'s
    own original casing. decompose() cleans (lowercases) internally
    to match graphemes, but for these simple alphabetic story words
    (no apostrophes/punctuation to strip) its grapheme spans line up
    1:1 with `word`'s own character positions either way, so blanking
    directly into `word` itself -- not a pre-lowercased copy of it --
    preserves whatever casing the caller actually passed in."""
    chars = list(word)
    for grapheme in decompose(word).graphemes:
        if grapheme.kind == "V":
            start, end = grapheme.span
            for i in range(start, end):
                chars[i] = "_"
    return "".join(chars)


def find_word_occurrence(pages: list[str], clean_target: str) -> tuple[int, int, str] | None:
    """Decision 0112: the first occurrence of `clean_target` (already
    `clean_word()`-ed, e.g. from pick_game_words()) in `pages`,
    as `(page_index, word_index, original_text)` -- `original_text`
    keeps whatever casing/punctuation it actually has on the page
    (e.g. "Sam" at the start of a sentence), unlike `clean_target`
    itself. `word_index` is the word's own position within that one
    page's `.split(" ")`, matching screen_face.py's own wrapped-line
    word-position convention (device/screen_face.py's
    set_reading_text_highlight()/_draw_reading_lines_static()) -- what
    lets the word game highlight this exact word in place, not a
    separate isolated view. `None` if the word isn't on any page at
    all (shouldn't happen for a word pick_game_words() itself sourced
    from book.words, but a safe, explicit miss rather than an
    IndexError if it ever does)."""
    for page_index, page in enumerate(pages):
        for word_index, raw in enumerate(page.split()):
            if clean_word(raw) == clean_target:
                return page_index, word_index, raw
    return None


def is_correct_answer(word: str, spoken: str) -> bool:
    """Lenient on purpose: true if the target word appears anywhere in
    the child's reply, so a child who spells the missing letters out
    first and then says the whole word still gets credit -- the same
    "don't penalize extra talk" spirit reading/hints.py's own matching
    already follows."""
    return clean_word(word) in tokenize(spoken)


def incorrect_response(word: str) -> str:
    return _INCORRECT_TEMPLATE.format(word=word, breakdown=blend_breakdown(word))


def random_closing_line() -> str:
    return random.choice(_CLOSING_LINES)


def build_word_game_reaction_prompt(
    story_text: str, results: list[tuple[str, bool]], age: int | None
) -> str:
    """Decision 0112: asks for ONE short, warm reaction covering every
    missing word at once -- not a separate reply per word, the way the
    old per-word canned-response pools worked turn by turn. Each
    word's own correctness is already decided by is_correct_answer()
    (passed in as `results`), never left to the model to judge --
    same reasoning reading/comprehension.py's build_reaction_prompt()
    already established (decisions 0083/0097): a cheap, exact check
    beats trusting a model's own correctness judgment when one is
    available.

    Decision 0118: no longer hands over hints.py's own blend_breakdown()
    text for a wrong word -- the whole point of decision 0116 was no
    more phonics teaching anywhere in this flow, and this was the one
    place still doing it. For anything wrong, the model just names the
    real word and moves on warmly, same spirit as the simplified hint-
    ladder replacement's own "That's okay! The word is 'X'." reaction."""
    age_line = f"The child is about {age} years old. " if age else ""
    word_lines = []
    for word, correct in results:
        if correct:
            word_lines.append(f'- "{word}": correct.')
        else:
            word_lines.append(f'- "{word}": incorrect. The real word is "{word}".')
    words_phrase = "words hidden" if len(results) > 1 else "a word hidden"
    return (
        f"{age_line}You are Chitti, a friendly companion robot. You just played a "
        f'"missing letters" word game with a child, using {words_phrase} in a '
        f"story they just read. Here's how they did on each word -- already decided, "
        "do not re-judge correctness yourself:\n"
        + "\n".join(word_lines)
        + "\n\nWrite ONE short, warm, combined reaction covering every word above -- "
        "celebrate what was right, and for anything wrong, gently name the real word "
        "and encourage them -- no phonics breakdown, no sounding it out, just the word "
        "itself. Use ONLY the facts given above and the story text below -- never "
        "invent new details. Keep it to two or three short sentences, simple and "
        "encouraging either way.\n\n"
        f"STORY:\n{story_text}"
    )
