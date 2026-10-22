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

_ACTIVITY_KEYWORDS = (
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
)


def detect_intent_phrase(text: str) -> str | None:
    if _STORY_PATTERN.search(text):
        return STORY
    if _READ_PATTERN.search(text):
        return READ
    if _SONG_PATTERN.search(text):
        return SONG
    if _CHAT_PATTERN.search(text):
        return CHAT
    if _TEACH_PATTERN.search(text):
        return TEACH
    return None


def mentions_activity_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _ACTIVITY_KEYWORDS)


_AFFIRMATIVE_WORDS = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "right", "correct", "please",
}
_NEGATIVE_WORDS = {"no", "nope", "nah", "not"}


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
    """
    for raw_word in text.lower().split():
        word = re.sub(r"[^\w']", "", raw_word)
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
