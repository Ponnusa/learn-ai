"""Graduated hint ladder for a struggling word (decision 0052) -- no
LLM call, by design, same instinct as feedback.py.

Deliberately post-hoc, not live: Chitti's audio capture
(voice_loop_demo._capture_and_transcribe) is push-to-talk -- record
until Enter, then transcribe once. There's no streaming/partial
transcription or voice-activity detection, so there's no way to notice
a child pausing mid-sentence and jump in. The feasible shape is: let
the child finish the whole passage, grade it, then -- if grading
surfaced a real miss -- offer a short hint-and-retry exchange for that
one word before the normal feedback. One hint-word per book in V1.
"""
from .alignment import OMISSION, SUBSTITUTION
from .curriculum import DEFAULT_SIGHT_WORDS
from .decodability import clean_word, decompose
from .schema import AssessmentResult

# Public (not underscore-prefixed): voice_loop_demo.py's orchestration
# loop needs this count to stay in sync with build_hint_line()'s own
# stage count, rather than a second hardcoded "4" living in a
# different file that could silently drift out of sync.
HINT_STAGES = 4

# Decision 0064: a hint needs to say the actual phonics *sound*, not
# a letter name -- "that word starts with the 'f' sound" handed to
# TTS is very likely spoken as the letter name "eff," not the phoneme
# /f/. Rather than gamble on a respelled string like "fff" (whether
# any given TTS engine pronounces that as intended is genuinely
# unverifiable from here), every grapheme maps to a short, common,
# reliably-pronounced example word instead -- "the same sound as in
# 'fish'" can't be mispronounced the way a made-up phonetic spelling
# can. Covers every grapheme decodability.decompose() can actually
# return (plain letters, digraphs, silent-e pairs, r-controlled,
# vowel teams, glued sounds, y-as-vowel) -- never the structural
# sentinels ("_blend_", "-s"/"-ed"/...), which decompose() itself
# never produces as a real grapheme string.
_SOUND_EXAMPLES: dict[str, str] = {
    # short_vowels -- vowels
    "a": "cat", "e": "bed", "i": "pig", "o": "dog", "u": "sun",
    # short_vowels -- consonants
    "b": "bat", "c": "cat", "d": "dog", "f": "fish", "g": "goat",
    "h": "hat", "j": "jam", "k": "kite", "l": "log", "m": "mat",
    "n": "net", "p": "pig", "q": "quick", "r": "run", "s": "sun",
    "t": "top", "v": "van", "w": "wet", "x": "fox", "z": "zip",
    # digraphs
    "sh": "ship", "ch": "chip", "th": "that", "wh": "whale",
    "ck": "duck", "ng": "sing", "ph": "phone", "qu": "quick",
    # silent_e (long-vowel patterns)
    "a_e": "cake", "e_e": "these", "i_e": "bike", "o_e": "rope", "u_e": "cube",
    # r_controlled
    "ar": "car", "er": "her", "ir": "bird", "or": "for", "ur": "fur",
    # vowel_teams
    "ai": "rain", "ay": "day", "ee": "bee", "ea": "sea", "oa": "boat",
    "oe": "toe", "ie": "pie", "igh": "light", "oo": "moon", "ou": "out",
    "ow": "cow", "oi": "coin", "oy": "boy", "au": "sauce", "aw": "saw",
    # glued_sounds
    "all": "ball", "ang": "bang", "ing": "king", "ong": "song", "ung": "sung",
    "ank": "bank", "ink": "pink", "onk": "honk", "unk": "trunk",
    # y_vowel
    "y": "my",
}

# Found live: a 1-2 letter word like "a" or "I" got selected as a hint
# target -- "that word starts with the 'a' sound" is nonsensical for a
# word that IS the sound, nothing to graduate into sounding out. 3
# letters is deliberately the level this curriculum's own shortest
# real phonics targets sit at (CVC words like "cat"/"sat"/"mat") --
# short enough to keep those, long enough to skip trivial function words.
_MIN_HINT_WORD_LENGTH = 3

# Decision 0058, also found live: "the" passed the length check above
# but is a sight word (curriculum.DEFAULT_SIGHT_WORDS) -- meant to be
# recognized by memory, not sounded out. "Let's sound it out: th-e"
# doesn't apply to it, and the child's actual reply ("Duh!") read as
# genuine annoyance at being asked to sound out something that trivial.
_SIGHT_WORDS = {clean_word(w) for w in DEFAULT_SIGHT_WORDS}


def is_worth_practicing(word: str) -> bool:
    """True if `word` is substantial enough to practice -- not
    trivially short, not a sight word (meant to be recognized by
    memory, not decoded). Shared by pick_hint_word() and
    feedback.py's own practice-word list (decision 0060), so both
    apply exactly the same bar for "a real word worth calling out,"
    not two definitions that can drift apart."""
    return len(word) >= _MIN_HINT_WORD_LENGTH and clean_word(word) not in _SIGHT_WORDS


# Decision 0065: how many real misses get the interactive hint-and-
# retry ladder in one book -- matches feedback.py's own
# _MAX_PRACTICE_WORDS, so the spoken practice-words summary and what
# was actually hinted on live agree on the same cap.
_MAX_HINT_WORDS = 3


def pick_hint_words(assessment: AssessmentResult, max_words: int = _MAX_HINT_WORDS) -> list[str]:
    """Every real-error word (substitution/omission) worth a
    graduated hint, deduped, in reading order, capped at `max_words`
    -- decision 0065: every real miss gets the ladder, not just the
    first. self_correction/hesitation/insertion miscues are skipped --
    assess() itself already treats those as not the child's fault.
    Words that aren't is_worth_practicing() are skipped too."""
    seen: set[str] = set()
    words: list[str] = []
    for miscue in assessment.miscues:
        if (
            miscue.kind in (SUBSTITUTION, OMISSION)
            and miscue.expected
            and is_worth_practicing(miscue.expected)
        ):
            cleaned = clean_word(miscue.expected)
            if cleaned in seen:
                continue
            seen.add(cleaned)
            words.append(miscue.expected)
            if len(words) >= max_words:
                break
    return words


def pick_hint_word(assessment: AssessmentResult) -> str | None:
    """Returns the first real-error word worth a graduated hint, or
    None if there isn't one -- a single-result convenience wrapper
    around pick_hint_words(), kept for callers that only ever want
    one (e.g. existing tests)."""
    words = pick_hint_words(assessment, max_words=1)
    return words[0] if words else None


def build_hint_line(word: str, stage: int) -> str:
    """stage 0: encourage + sound-it-out. stage 1: first-sound hint
    (an example word, not a letter name or a guessed-at respelling).
    stage 2 (decision 0064, new): the full sound-by-sound breakdown,
    then blended -- the "f-r-o-g, now blend it: frog" step the
    original 3-stage ladder never had. stage 3: say the word and
    invite one more try. Mirrors the source product's own graduated-
    hint content, applied after the read instead of during it."""
    if stage == 0:
        return "Let's try that word again -- take your time and sound it out."
    if stage == 1:
        first_example = _sound_example(_first_grapheme(word))
        return f"Here's a hint: that word starts with the same sound as '{first_example}'."
    if stage == 2:
        return f"Let's sound it out together: {blend_breakdown(word)}. Now blend it: {word}."
    return f'That word is "{word}" -- can you say it back to me?'


def _first_grapheme(word: str) -> str:
    graphemes = decompose(word).graphemes
    return graphemes[0].grapheme if graphemes else word[0]


def _sound_example(grapheme: str) -> str:
    return _SOUND_EXAMPLES.get(grapheme, grapheme)


def blend_breakdown(word: str) -> str:
    """"frog" -> "'f' like in 'fish', 'r' like in 'run', 'o' like in
    'dog', 'g' like in 'goat'" -- every grapheme in reading order,
    each tied to a reliably-pronounced example word. Public (not
    underscore-prefixed): decision 0070 (now 0112's
    build_word_game_reaction_prompt()) reuses this exact breakdown in
    word_game.py, so the bonus game explains a missed word's sounds
    the same way the hint ladder does, rather than a second phonics
    explanation that could drift out of sync."""
    graphemes = decompose(word).graphemes
    if not graphemes:
        return word
    parts = [
        f"'{g.grapheme}' like in '{_sound_example(g.grapheme)}'" for g in graphemes
    ]
    return ", ".join(parts)
