"""Word-family generalization check (decision 0066) -- once a word is
read successfully, offer a small set of same-pattern words (same
rime, different onset: mat -> cat, sat, bat, rat) so the child's skill
is tested against new words, not just the one just read.

Same verifier-gated shape every other generation path in this package
uses (book_generation.py's decodability retry loop, comprehension.py's
screen-and-drop): the LLM *proposes* candidate words, but whether a
candidate actually shares the target rime and is decodable at the
child's current level is a deterministic check against
decodability.py, not something trusted on the model's say-so. A
candidate that fails either check is simply dropped -- there's no
single "fix" for a bad rhyme the way there is for a decodability
violation, so this follows comprehension.py's simpler screen-and-drop
precedent, not book_generation.py's heavier feed-back-and-retry loop.
"""
from .decodability import GraphemeHit, clean_word, decompose, is_word_decodable


def extract_rime(word: str) -> tuple[str, list[GraphemeHit]] | None:
    """Splits `word` into its onset (first grapheme) and rime (every
    grapheme after it), returning the rime's plain spelling alongside
    its structured graphemes -- the spelling for the LLM prompt, the
    graphemes for verify_family_word()'s exact-match check. None for a
    word with only one grapheme (e.g. "a"): nothing left to vary."""
    graphemes = decompose(word).graphemes
    if len(graphemes) <= 1:
        return None
    rime_graphemes = graphemes[1:]
    rime_spelling = "".join(g.grapheme for g in rime_graphemes)
    return rime_spelling, rime_graphemes


def build_family_prompt(word: str, rime_spelling: str, num_words: int = 4) -> str:
    """Asks for simple, real, same-pattern words sharing `word`'s rime
    -- same `WORD:`-per-line convention as every other generation
    prompt in this codebase (book_generation.py, comprehension.py)."""
    return (
        "You are Chitti, a friendly companion robot helping a child practice "
        f'phonics. A child just read the word "{word}" correctly. Write '
        f"{num_words} other simple, real English words that end in \"-{rime_spelling}\", "
        f'the same way "{word}" does -- just a different starting sound or letter. '
        "Use only common, simple words a young child would already know.\n\n"
        'Reply with exactly one word per line, each starting with "WORD:", nothing else.'
    )


def parse_family_words(reply_text: str) -> list[str]:
    """Parses the WORD:-per-line format build_family_prompt() asks
    for. Same strict-but-forgiving style as comprehension.py's
    parse_questions()."""
    words: list[str] = []
    for line in reply_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("WORD:"):
            word = line.split(":", 1)[1].strip()
            if word:
                words.append(word)
    return words


def verify_family_word(
    candidate: str, target_rime_graphemes: list[GraphemeHit], mastered_levels: list[str]
) -> bool:
    """True only if `candidate` actually shares the target rime --
    exactly the same grapheme sequence after its own onset, not just
    an approximate rhyme -- and is decodable at the child's current
    phonics budget. Either check failing drops the candidate."""
    cleaned = clean_word(candidate)
    candidate_graphemes = decompose(cleaned).graphemes
    if len(candidate_graphemes) <= 1:
        return False
    candidate_rime = [g.grapheme for g in candidate_graphemes[1:]]
    target_rime = [g.grapheme for g in target_rime_graphemes]
    if candidate_rime != target_rime:
        return False
    return is_word_decodable(cleaned, mastered_levels)
