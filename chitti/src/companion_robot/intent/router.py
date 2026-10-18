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
SONG = "SONG"
CHAT = "CHAT"
TEACH = "TEACH"

_STORY_PATTERN = re.compile(
    r"\b(tell|read)\s+(me\s+)?a\s+story\b|\bstory\s*time\b", re.IGNORECASE
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
    """
    for word in text.lower().split():
        if word in _NEGATIVE_WORDS:
            return False
        if word in _AFFIRMATIVE_WORDS:
            return True
    return False
