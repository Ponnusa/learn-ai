"""Deterministic phrase-trigger for mode-switching (decision 0042) --
the cheap first pass before any LLM classification call. Modeled on
education/math_check.py's style: pure functions, returns None on
anything unrecognized rather than guessing.

detect_intent_phrase() catches clear, common phrasings for free.
mentions_activity_keyword() is a separate, looser gate: voice_loop_demo.py
only calls the LLM fallback (ConversationService.classify_intent()) when
this returns True, so an ordinary conversational turn that never
mentions a story/song/chat/teach never pays for an extra LLM call --
real switch requests almost always name the activity.
"""
import re

STORY = "STORY"
READ = "READ"
SONG = "SONG"
CHAT = "CHAT"
TEACH = "TEACH"

_STORY_PATTERN = re.compile(
    r"\b(tell|read)\s+(me\s+)?a\s+story\b|\bstory\s*time\b", re.IGNORECASE
)
# Decision 0051: deliberately distinct from _STORY_PATTERN above -- that
# one is "Chitti reads TO the child" (needs "a story"); this one is
# "the child wants to read OUT LOUD themselves", so none of these
# phrasings include "a story". Checked after _STORY_PATTERN in
# detect_intent_phrase() so an ambiguous "I want to read a story"
# still resolves to the existing, more specific STORY match.
_READ_PATTERN = re.compile(
    r"\b(i\s+want\s+to|let\s+me|i'?ll|can\s+i|help\s+me(\s+practice)?)\s+read\b|"
    r"\breading\s+practice\b|\bpractice\s+(my\s+)?reading\b",
    re.IGNORECASE,
)
_SONG_PATTERN = re.compile(
    r"\b(play|sing)\s+(me\s+)?a\s+(song|lullaby)\b|\bplay\s+(some\s+)?music\b",
    re.IGNORECASE,
)
_CHAT_PATTERN = re.compile(
    r"\blet'?s\s+(just\s+)?(talk|chat|play)\b|\bstop\s+the\s+story\b", re.IGNORECASE
)
_TEACH_PATTERN = re.compile(
    r"\b(let\s+me|i\s+want\s+to|i'?ll)\s+teach\s+you\b", re.IGNORECASE
)

_ACTIVITY_KEYWORDS = {
    "story",
    "stories",
    "read",
    "reading",
    "song",
    "songs",
    "sing",
    "lullaby",
    "lullabies",
    "music",
    "chat",
    "talk",
    "teach",
}

# Decision 0127, found live: a plain phrase search has no way to tell
# "tell me a story" (a request) apart from "don't tell me a story" (a
# refusal) -- .search() matches the phrase anywhere in the text
# regardless of what precedes it. Deliberately narrow: a fixed, small
# lookback window and a fixed word list, catching the common "don't
# X"/"let's not X" shape right before the activity verb, not full
# negation-scope parsing (which phrase-based matching was never going
# to get right in general anyway).
_PHRASE_NEGATION_WORDS = {"don't", "dont", "not", "never", "no"}
_NEGATION_LOOKBACK_WORDS = 3


def _negated_before(text: str, match_start: int) -> bool:
    preceding_words = re.findall(r"[a-z']+", text[:match_start].lower())
    return any(w in _PHRASE_NEGATION_WORDS for w in preceding_words[-_NEGATION_LOOKBACK_WORDS:])


def detect_intent_phrase(text: str) -> str | None:
    for pattern, label in (
        (_STORY_PATTERN, STORY),
        (_READ_PATTERN, READ),
        (_SONG_PATTERN, SONG),
        (_CHAT_PATTERN, CHAT),
        (_TEACH_PATTERN, TEACH),
    ):
        match = pattern.search(text)
        if match and not _negated_before(text, match.start()):
            return label
    return None


def mentions_activity_keyword(text: str) -> bool:
    """Decision 0127, found live: a plain substring check matched
    "read" inside "already" and "sing" inside "using" -- real phrases
    a child might actually say, each wrongly triggering the (paid) LLM
    classification fallback. Tokenizes to whole words first, then
    checks whether a keyword starts a word -- not exact-word-only
    matching, which would miss legitimate inflections like "talking"
    (from "talk") or "teaching" (from "teach") the same way "read"
    inside "already" was never supposed to match: a keyword appearing
    mid-word is the bug, a keyword appearing at the start of a longer
    word (letting its own suffix follow) is not."""
    words = re.findall(r"[a-z']+", text.lower())
    return any(word.startswith(keyword) for word in words for keyword in _ACTIVITY_KEYWORDS)


_AFFIRMATIVE_WORDS = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "right", "correct", "please",
}
_NEGATIVE_WORDS = {"no", "nope", "nah", "not"}

# Decision 0127: see classify_affirmative()'s own note -- a word
# right before one of these means "ignore everything I said before
# this point," so only a signal word AFTER the last one found counts.
_CORRECTION_MARKERS = {"actually", "wait", "mean"}


def classify_affirmative(text: str) -> bool | None:
    """The same word-order-sensitive yes/no walk `is_affirmative()`
    uses, but returns `None` rather than a hard `False` when no
    signal word of either kind appears at all -- decision 0079, found
    live: a reply like "The little forg" (an attempt to start reading
    a story back, not an answer to the yes/no question at all) has no
    "yes" or "no" in it, and a caller that treats that silence the
    same as an explicit decline can permanently lose a one-time offer
    over a reply that was never actually a "no." Most callers still
    only care about "was this a yes" (`is_affirmative()`, below); a
    caller that needs to tell "declined" apart from "didn't answer
    this question at all" -- so it can ask again later instead of
    giving up -- uses this directly.

    Decision 0127, found live: "first signal word wins" (see
    is_affirmative()'s own addendum below) reads "Okay, actually no."
    as a yes -- "okay" is the first signal word, and the self-
    correction right after it is never considered. If a correction
    marker ("actually"/"wait"/"mean", e.g. "I mean") appears anywhere
    in the reply, only the signal words AFTER the LAST one count --
    otherwise this falls back to the existing first-wins behavior
    unchanged, so the original addendum's own case ("yes my friend is
    not talking to me...") still resolves the same way."""
    words = re.findall(r"[a-z']+", text.lower())
    start = 0
    for i, word in enumerate(words):
        if word in _CORRECTION_MARKERS:
            start = i + 1
    for word in words[start:]:
        if word in _NEGATIVE_WORDS:
            return False
        if word in _AFFIRMATIVE_WORDS:
            return True
    return None


def is_affirmative(text: str) -> bool:
    """Decision 0046: deterministic yes/no parsing for the switch-
    confirmation question -- word-list based, same pure-function style
    as detect_intent_phrase(). Defaults to False (don't switch) when no
    signal word appears at all -- same safer-default instinct
    _pick_item_by_voice()'s retry already uses.

    Addendum, found live: a real "yes my friend is not talking to me
    my friend is not talking to me" (a genuine yes, repeated for
    emphasis) was misread as a decline, because the original "any
    negative word anywhere in the reply wins" rule let the unrelated
    "not" (from restating the complaint, not negating the answer)
    override the "yes" that actually opened the sentence. People
    answer yes/no questions by leading with the answer, so this now
    walks the words in order and returns on the FIRST signal word --
    position, not "negative always wins" -- carries the real answer.

    Second addendum, also found live: a real "Yes." -- a one-word
    affirmative with the trailing period Whisper commonly adds --
    returned False. `text.lower().split()` never stripped punctuation
    per word, so "yes." never equals "yes" in _AFFIRMATIVE_WORDS and
    silently fell through to the safer-default False, mis-reading a
    genuine yes as a decline. Every word is now stripped of anything
    that isn't a letter/digit/apostrophe before matching.
    """
    return classify_affirmative(text) is True
