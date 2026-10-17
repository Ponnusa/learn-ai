"""Unit tests for decision 0042's hybrid intent detection and voice
picker in voice_loop_demo.py -- real ConversationService/repositories,
fake LLM/tts/audio/stt stand-ins, no real API calls, hardware, or
keyboard input() needed.
"""
from unittest.mock import AsyncMock, patch

from companion_robot.conversation.service import ConversationService
from companion_robot.device.interfaces import DeviceState
from companion_robot.engagement.repository import EngagementRepository
from companion_robot.engagement.schema import EngagementMode
from companion_robot.memory.repository import MemoryRepository
from companion_robot.storage.sqlite import connect
from companion_robot.transcripts.repository import TranscriptRepository
from companion_robot.voice.interfaces import LanguageModelBackend
from companion_robot.voice_loop_demo import (
    _detect_switch_intent,
    _pick_item_by_voice,
    _resolve_spoken_choice,
    _run_teachable_friend,
)


class _FakeLLM(LanguageModelBackend):
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[list[dict], str]] = []

    async def generate_reply(self, messages, system_prompt):
        self.calls.append((messages, system_prompt))
        return self.reply, "fake-model"


class _FakeAudio:
    async def play(self, audio_bytes: bytes) -> None:
        pass

    async def stop_playback(self) -> None:
        pass


class _FakeTTS:
    def __init__(self) -> None:
        self.synthesized: list[str] = []

    async def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        self.synthesized.append(text)
        return b"fake-audio"


class _FakeFace:
    def __init__(self) -> None:
        self.states: list[DeviceState] = []

    def set_status_led(self, state: DeviceState) -> None:
        self.states.append(state)


class _Item:
    def __init__(self, title: str) -> None:
        self.title = title


# -- _detect_switch_intent -----------------------------------------------


async def test_detect_switch_intent_strict_phrase_match_skips_the_llm():
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)

    mode = await _detect_switch_intent("can you tell me a story", conversation)

    assert mode == "2"
    assert llm.calls == []  # strict phrase match never reaches classify_intent()


async def test_detect_switch_intent_no_activity_keyword_skips_the_llm():
    """The core cost-control property: an ordinary turn that never
    mentions an activity never pays for an extra LLM call."""
    llm = _FakeLLM(reply="STORY")
    conversation = ConversationService(llm)

    mode = await _detect_switch_intent("the cat has four legs", conversation)

    assert mode is None
    assert llm.calls == []


async def test_detect_switch_intent_ambiguous_phrasing_falls_back_to_the_llm():
    llm = _FakeLLM(reply="SONG")
    conversation = ConversationService(llm)

    mode = await _detect_switch_intent("I don't want a story, let's do something else musical", conversation)

    assert mode == "4"
    assert len(llm.calls) == 1


async def test_detect_switch_intent_llm_none_keeps_current_mode():
    llm = _FakeLLM(reply="NONE")
    conversation = ConversationService(llm)

    mode = await _detect_switch_intent("can we sing something later maybe", conversation)

    assert mode is None


# -- _resolve_spoken_choice -----------------------------------------------


def test_resolve_spoken_choice_exact_title_match():
    items = [_Item("The Fox"), _Item("Hush Little Baby")]
    assert _resolve_spoken_choice("I want hush little baby", items) is items[1]


def test_resolve_spoken_choice_ordinal_word():
    items = [_Item("The Fox"), _Item("Hush Little Baby")]
    assert _resolve_spoken_choice("the second one please", items) is items[1]


def test_resolve_spoken_choice_fuzzy_match():
    items = [_Item("The Fox"), _Item("Hush Little Baby")]
    assert _resolve_spoken_choice("the fox one", items) is items[0]


def test_resolve_spoken_choice_defaults_to_first_on_no_match():
    items = [_Item("The Fox"), _Item("Hush Little Baby")]
    assert _resolve_spoken_choice("completely unrelated gibberish", items) is items[0]


# -- _pick_item_by_voice ---------------------------------------------------


async def test_pick_item_by_voice_single_item_asks_nothing():
    tts = _FakeTTS()
    item = await _pick_item_by_voice([_Item("Only One")], "stories", tts, None, _FakeAudio(), _FakeFace(), 1.0)

    assert item.title == "Only One"
    assert tts.synthesized == []  # no question asked for a single item


async def test_pick_item_by_voice_multiple_items_speaks_and_listens():
    items = [_Item("The Fox"), _Item("Hush Little Baby")]
    tts = _FakeTTS()
    face = _FakeFace()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        return_value="hush little baby",
    ):
        item = await _pick_item_by_voice(items, "lullabies", tts, "fake-stt", _FakeAudio(), face, 1.0)

    assert item is items[1]
    assert len(tts.synthesized) == 1
    assert "The Fox" in tts.synthesized[0] and "Hush Little Baby" in tts.synthesized[0]
    assert DeviceState.SPEAKING in face.states
    assert DeviceState.LISTENING in face.states


# -- a mode loop actually switching, end to end ----------------------------


async def test_run_teachable_friend_switches_mode_on_detected_intent():
    """The actual integration under test: a turn detected as a switch
    request breaks the loop (running the existing finally cleanup)
    instead of ever reaching teachable_friend_reply() for that turn,
    and returns the mode code main() uses to dispatch next -- while an
    earlier, ordinary turn in the same session still got a real reply
    and is still included in the finally cleanup's recordings."""
    conn = connect(":memory:")
    memories = MemoryRepository(conn)
    engagement = EngagementRepository(conn)
    transcripts = TranscriptRepository(conn)
    llm = _FakeLLM(reply="Dogs are great, tell me more!")
    summarizer = _FakeLLM(reply="NOTHING")
    conversation = ConversationService(llm, summarizer_llm=summarizer)
    face = _FakeFace()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=["dogs are my favorite animal", "tell me a story please"],
    ):
        next_mode = await _run_teachable_friend(
            conversation, _FakeTTS(), _FakeAudio(), "fake-stt",
            memories, engagement, transcripts, face, "child-1", 1.0,
        )

    assert next_mode == "2"
    assert len(llm.calls) == 1  # only the first, ordinary turn reached teachable_friend_reply()
    assert len(engagement.list_for_child("child-1")) == 1  # finally cleanup still ran
    assert len(transcripts.list_for_child("child-1")) == 1
