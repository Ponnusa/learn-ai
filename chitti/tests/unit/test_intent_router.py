"""Unit tests for companion_robot.intent.router -- pure functions, no
LLM/IO needed.
"""
from companion_robot.intent.router import (
    CHAT,
    SONG,
    STORY,
    TEACH,
    detect_intent_phrase,
    mentions_activity_keyword,
)


def test_detects_story_request():
    assert detect_intent_phrase("can you tell me a story") == STORY
    assert detect_intent_phrase("read me a story please") == STORY
    assert detect_intent_phrase("I want story time now") == STORY


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


def test_mentions_activity_keyword_true_cases():
    assert mentions_activity_keyword("I don't want a story, let's chat instead") is True
    assert mentions_activity_keyword("can we sing something") is True


def test_mentions_activity_keyword_false_for_ordinary_turns():
    assert mentions_activity_keyword("the cat has four legs") is False
    assert mentions_activity_keyword("two plus two is four") is False
