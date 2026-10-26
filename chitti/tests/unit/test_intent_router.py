"""Unit tests for companion_robot.intent.router -- pure functions, no
LLM/IO needed.
"""
from companion_robot.intent.router import (
    CHAT,
    READ,
    SONG,
    STORY,
    TEACH,
    classify_affirmative,
    detect_intent_phrase,
    is_affirmative,
    mentions_activity_keyword,
)


def test_detects_story_request():
    assert detect_intent_phrase("can you tell me a story") == STORY
    assert detect_intent_phrase("read me a story please") == STORY
    assert detect_intent_phrase("I want story time now") == STORY


def test_detects_read_request():
    assert detect_intent_phrase("I want to read") == READ
    assert detect_intent_phrase("let me read") == READ
    assert detect_intent_phrase("can I read now") == READ
    assert detect_intent_phrase("I'll read") == READ
    assert detect_intent_phrase("help me practice reading") == READ
    assert detect_intent_phrase("reading practice please") == READ
    assert detect_intent_phrase("I want to practice my reading") == READ


def test_ambiguous_read_a_story_resolves_to_story_not_read():
    """Decision 0051: _STORY_PATTERN is checked first in
    detect_intent_phrase() specifically so this stays STORY -- Chitti
    reading TO the child, not the child reading out loud."""
    assert detect_intent_phrase("I want to read a story") == STORY
    assert detect_intent_phrase("can you read me a story") == STORY


def test_detects_song_request():
    assert detect_intent_phrase("play a song for me") == SONG
    assert detect_intent_phrase("sing me a lullaby") == SONG
    assert detect_intent_phrase("can you play some music") == SONG


def test_detects_chat_request():
    assert detect_intent_phrase("let's just talk") == CHAT
    assert detect_intent_phrase("can we stop the story") == CHAT


def test_detects_teach_request():
    assert detect_intent_phrase("I want to teach you something") == TEACH
    assert detect_intent_phrase("let me teach you about dinosaurs") == TEACH


def test_returns_none_for_ordinary_conversation():
    assert detect_intent_phrase("the cat has four legs") is None
    assert detect_intent_phrase("two plus two is four") is None
    assert detect_intent_phrase("") is None


def test_detect_intent_phrase_ignores_a_negated_request():
    """Decision 0127, found live: a plain phrase search matches "tell
    me a story" anywhere in the text, with no way to tell a request
    apart from a refusal of the same phrasing."""
    assert detect_intent_phrase("Don't tell me a story.") is None
    assert detect_intent_phrase("Let's not sing a song.") is None


def test_detect_intent_phrase_negation_guard_does_not_catch_unrelated_stop_requests():
    """The negation guard is a narrow lookback right before the
    matched phrase -- "stop reading" (a different activity, not a
    negation of the one actually requested) must not suppress the
    real request that follows it."""
    assert detect_intent_phrase("Stop reading and tell me a story.") == STORY


def test_mentions_activity_keyword_true_cases():
    assert mentions_activity_keyword("I don't want a story, let's chat instead") is True
    assert mentions_activity_keyword("can we sing something") is True
    assert mentions_activity_keyword("I'd like to do some reading") is True


def test_mentions_activity_keyword_false_for_ordinary_turns():
    assert mentions_activity_keyword("the cat has four legs") is False
    assert mentions_activity_keyword("two plus two is four") is False


def test_mentions_activity_keyword_ignores_substring_false_positives():
    """Decision 0127, found live: a plain substring check matched
    "read" inside "already" and "sing" inside "using" -- real,
    unrelated phrases that wrongly paid for an LLM classification
    call. Whole-word matching only."""
    assert mentions_activity_keyword("I already finished my homework") is False
    assert mentions_activity_keyword("I'm using the bathroom") is False


def test_is_affirmative_clear_yes():
    assert is_affirmative("yes") is True
    assert is_affirmative("yeah sure") is True
    assert is_affirmative("okay that's right") is True


def test_is_affirmative_clear_no():
    assert is_affirmative("no") is False
    assert is_affirmative("nope not really") is False


def test_is_affirmative_strips_trailing_punctuation():
    """Found live: a real "Yes." (the trailing period Whisper commonly
    adds) returned False -- the word never got stripped of punctuation
    before matching against _AFFIRMATIVE_WORDS, silently mis-reading a
    genuine yes as a decline (the word game was offered, the child
    said "Yes.", and it was skipped entirely)."""
    assert is_affirmative("Yes.") is True
    assert is_affirmative("No.") is False
    assert is_affirmative("Sure!") is True
    assert is_affirmative("okay, let's do it") is True


def test_is_affirmative_defaults_to_false_for_unclear_or_empty():
    assert is_affirmative("") is False
    assert is_affirmative("maybe later") is False


def test_is_affirmative_negative_first_word_wins():
    assert is_affirmative("no that's not what I meant") is False


def test_is_affirmative_first_signal_word_wins_over_a_later_unrelated_negative():
    """Decision 0046 addendum, found live: a real "yes my friend is
    not talking to me my friend is not talking to me" (a genuine yes,
    repeated for emphasis) was misread as a decline because it
    contains "not" later in the sentence. People lead with their
    answer, so the first signal word -- not any negative word anywhere
    -- is what actually carries it."""
    assert is_affirmative("yes my friend is not talking to me") is True


def test_classify_affirmative_returns_true_for_a_clear_yes():
    assert classify_affirmative("yes") is True
    assert classify_affirmative("sure, let's do it") is True


def test_classify_affirmative_returns_false_for_a_clear_no():
    assert classify_affirmative("no") is False
    assert classify_affirmative("nope not really") is False


def test_classify_affirmative_respects_a_self_correction():
    """Decision 0127, found live: "first signal word wins" (the
    decision 0046 addendum below) reads "Okay, actually no." as a
    yes -- "okay" is the first signal word, and the self-correction
    right after it was never considered. A correction marker means
    only the signal words after it count."""
    assert classify_affirmative("Okay, actually no.") is False
    assert classify_affirmative("Yes-- wait, no.") is False
    assert classify_affirmative("No, I mean yes, let's do it.") is True


def test_classify_affirmative_self_correction_fix_does_not_regress_the_original_addendum():
    """The fix above must not reintroduce the failure decision 0046's
    own addendum already fixed -- this has no correction marker at
    all, so the existing first-signal-word-wins behavior must still
    apply unchanged."""
    assert classify_affirmative("yes my friend is not talking to me") is True


def test_classify_affirmative_returns_none_when_no_signal_word_appears():
    """Decision 0079, found live: a reply like "The little forg" (an
    attempt to start reading a story back, not an answer to the yes/
    no question at all) has no "yes" or "no" in it -- a caller that
    needs to tell "declined" apart from "didn't answer at all" (so it
    can ask again later instead of giving up a one-time offer) relies
    on this, unlike is_affirmative()'s own flat False for the same
    input."""
    assert classify_affirmative("") is None
    assert classify_affirmative("maybe later") is None
    assert classify_affirmative("The little forg") is None
