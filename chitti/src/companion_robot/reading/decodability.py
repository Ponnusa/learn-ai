"""Decodability engine (decision 0051) -- ported near-verbatim from
phono-storyforge's app/skills/decodability.py (Apache 2.0). Pure
algorithm: decompose(word) -> the ordered graphemes a word exercises,
each tagged with the phonics level that introduces it; check_decodability()
is the QA gate book_generation.py's verifier loop uses. No dependencies
beyond `re` and dataclasses -- this is exactly why it was worth porting
as-is rather than rebuilding: there's nothing Chitti-specific to adapt.
"""
import re
from dataclasses import dataclass, field

from .curriculum import DEFAULT_SIGHT_WORDS

VOWELS = set("aeiou")
# 'y' is treated as a consonant here except word-initial-vowel handling below.
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")

DIGRAPHS = {"sh", "ch", "th", "wh", "ck", "ng", "ph", "qu"}
R_CONTROLLED = {"ar", "er", "ir", "or", "ur"}
VOWEL_TEAMS = {
    "igh",
    "ai", "ay", "ee", "ea", "oa", "oe", "ie",
    "oo", "ou", "ow", "oi", "oy", "au", "aw",
}
# Welded/"glued" sounds: the vowel fuses with a following nasal or 'l' so
# the word cannot be sounded out letter-by-letter (e.g. 'ball' is /bɔl/).
GLUED_SOUNDS = {
    "all", "ang", "ing", "ong", "ung", "ank", "ink", "onk", "unk",
}
SUFFIXES = ("ing", "ed", "es", "s")

# Silent-e middle consonant excludes 'r' (V-r-e reads as r-controlled,
# e.g. 'more', 'here', not as a silent-e split vowel).
_SILENT_E_RE = re.compile(r"[aeiou][bcdfghjklmnpqstvwxyz]e$")


@dataclass
class GraphemeHit:
    """A single grapheme found in a word, tagged with its phonics level."""

    grapheme: str
    level: str
    span: tuple[int, int]
    kind: str  # "C" (consonant unit) or "V" (vowel unit)


@dataclass
class WordDecomposition:
    word: str
    graphemes: list[GraphemeHit]
    is_decodable: bool
    is_sight_word: bool
    violations: list[str] = field(default_factory=list)

    @property
    def grapheme_strings(self) -> list[str]:
        return [g.grapheme for g in self.graphemes]


def clean_word(word: str) -> str:
    """Strips punctuation, normalizes apostrophes, and lowercases a word."""
    word = word.replace("’", "'").strip().lower()
    word = re.sub(r"[^\w\s']", "", word)
    word = word.strip("'")
    return word


def _segment(word: str) -> list[GraphemeHit] | None:
    """Segments a cleaned word into ordered graphemes left-to-right.
    Returns None if a character can't be mapped to a known grapheme
    (which makes the word non-decodable by definition)."""
    n = len(word)
    if n == 0:
        return []

    se = _SILENT_E_RE.search(word)
    silent_vowel_idx = se.start() if se else None
    final_e_idx = n - 1 if se else None

    hits: list[GraphemeHit] = []
    i = 0
    while i < n:
        if final_e_idx is not None and i == final_e_idx:
            i += 1
            continue

        if silent_vowel_idx is not None and i == silent_vowel_idx:
            hits.append(GraphemeHit(word[i] + "_e", "silent_e", (i, final_e_idx + 1), "V"))
            i += 1
            continue

        ch = word[i]

        # Doubled consonant (floss rule: ff, ll, ss, zz, ...) -> one unit.
        if ch in CONSONANTS and i + 1 < n and word[i + 1] == ch:
            hits.append(GraphemeHit(ch, "short_vowels", (i, i + 2), "C"))
            i += 2
            continue

        matched = False
        for length in (3, 2):
            if i + length > n:
                continue
            if final_e_idx is not None and i < final_e_idx < i + length:
                continue
            seg = word[i : i + length]
            if seg in GLUED_SOUNDS:
                hits.append(GraphemeHit(seg, "glued_sounds", (i, i + length), "V"))
            elif seg in VOWEL_TEAMS:
                hits.append(GraphemeHit(seg, "vowel_teams", (i, i + length), "V"))
            elif seg in R_CONTROLLED:
                hits.append(GraphemeHit(seg, "r_controlled", (i, i + length), "V"))
            elif seg in DIGRAPHS:
                hits.append(GraphemeHit(seg, "digraphs", (i, i + length), "C"))
            else:
                continue
            i += length
            matched = True
            break
        if matched:
            continue

        if ch == "y":
            level, kind = ("short_vowels", "C") if i == 0 else ("y_vowel", "V")
            hits.append(GraphemeHit("y", level, (i, i + 1), kind))
        elif ch in VOWELS:
            hits.append(GraphemeHit(ch, "short_vowels", (i, i + 1), "V"))
        elif ch in CONSONANTS:
            hits.append(GraphemeHit(ch, "short_vowels", (i, i + 1), "C"))
        else:
            return None
        i += 1

    return hits


def _verdict(hits: list[GraphemeHit] | None, mastered_levels: list[str]) -> tuple[bool, list[str]]:
    if hits is None:
        return False, ["<unsegmentable>"]
    if not hits:
        return True, []
    if "short_vowels" not in mastered_levels:
        return False, [h.grapheme for h in hits]

    violations = [h.grapheme for h in hits if h.level not in mastered_levels]

    for a, b in zip(hits, hits[1:]):
        if a.kind == "C" and b.kind == "C" and "blends" not in mastered_levels:
            violations.append(f"{a.grapheme}{b.grapheme}")
        elif a.kind == "V" and b.kind == "V":
            violations.append(f"{a.grapheme}{b.grapheme}")

    return (len(violations) == 0), violations


def _suffix_bases(word: str):
    """Yields plausible base spellings after stripping an inflectional suffix."""
    if len(word) <= 2:
        return
    if word.endswith("ing") and len(word) >= 5:
        stem = word[:-3]
        yield stem
        yield stem + "e"
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            yield stem[:-1]
    if word.endswith("ed") and len(word) >= 4:
        stem = word[:-2]
        yield stem
        yield word[:-1]
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            yield stem[:-1]
    if word.endswith("es") and len(word) >= 4:
        yield word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) >= 3:
        yield word[:-1]


def inflectional_suffix(word: str) -> str | None:
    """Returns the inflectional suffix a word carries, else None -- the
    hook miscue attribution uses to map an inflected ending onto its
    -s/-es/-ed/-ing mastery sentinel."""
    w = clean_word(word)
    if w.endswith("ing") and len(w) >= 5:
        return "ing"
    if w.endswith("ed") and len(w) >= 4:
        return "ed"
    if w.endswith("es") and len(w) >= 4:
        return "es"
    if w.endswith("s") and not w.endswith("ss") and len(w) >= 3:
        return "s"
    return None


def _word_decodable(word: str, mastered_levels: list[str]) -> tuple[bool, list[str]]:
    hits = _segment(word)
    ok, violations = _verdict(hits, mastered_levels)
    if ok or "suffixes" not in mastered_levels:
        return ok, violations
    for base in _suffix_bases(word):
        base_ok, _ = _verdict(_segment(base), mastered_levels)
        if base_ok:
            return True, []
    return ok, violations


def decompose(
    raw_word: str,
    mastered_levels: list[str] | None = None,
    sight_words: set[str] | None = None,
) -> WordDecomposition:
    """Decomposes a word into graphemes and judges its decodability."""
    cleaned = clean_word(raw_word)
    sight = sight_words or set()
    is_sight = bool(cleaned) and cleaned in sight

    hits = _segment(cleaned)
    graphemes = hits or []

    if is_sight or not cleaned:
        return WordDecomposition(cleaned, graphemes, True, is_sight, [])

    decodable, violations = _word_decodable(cleaned, mastered_levels or [])
    return WordDecomposition(cleaned, graphemes, decodable, False, violations)


def is_word_decodable(word: str, mastered_levels: list[str]) -> bool:
    decodable, _ = _word_decodable(word.lower(), mastered_levels)
    return decodable


def check_decodability(story_text: str, phonics_profile: dict) -> dict:
    """Analyzes a story and returns decodability metrics for the
    verifier-gated book-generation loop (book_generation.py)."""
    mastered_levels = list(phonics_profile.get("mastered_levels", []))
    target_level = phonics_profile.get("target_level")
    if target_level and target_level not in mastered_levels:
        mastered_levels.append(target_level)

    sight_words = {clean_word(w) for w in phonics_profile.get("sight_words", [])}
    all_sight_words = sight_words | {clean_word(w) for w in DEFAULT_SIGHT_WORDS}

    violations: list[str] = []
    for raw_word in story_text.split():
        cleaned = clean_word(raw_word)
        if not cleaned or cleaned in all_sight_words:
            continue
        if not is_word_decodable(cleaned, mastered_levels):
            violations.append(raw_word)

    seen: set[str] = set()
    unique_violations: list[str] = []
    for v in violations:
        c = clean_word(v)
        if c not in seen:
            seen.add(c)
            unique_violations.append(v)

    is_decodable = len(unique_violations) == 0
    if is_decodable:
        feedback = "Story is 100% decodable based on the phonics profile."
    else:
        feedback = (
            "Story contains phonics violations. The following words are not "
            f"decodable for this level: {', '.join(unique_violations)}. "
            "Please rewrite the story to replace or remove these words."
        )

    return {"is_decodable": is_decodable, "violations": unique_violations, "feedback": feedback}
