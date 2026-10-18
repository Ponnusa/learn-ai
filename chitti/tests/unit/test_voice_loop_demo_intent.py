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
    _confirm_switch,
    _detect_switch_intent,
    _pick_item_by_voice,
    _resolve_spoken_choice,
    _run_everyday_companion,
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
        self.modes: list[str | None] = []

    def set_status_led(self, state: DeviceState) -> None:
        self.states.append(state)

    def set_expression_mode(self, mode: str | None) -> None:
        self.modes.append(mode)


class _Item:
    def __init__(self, title: str) -> None:
        self.title = title


# -- _detect_switch_intent -----------------------------------------------


async def test_detect_switch_intent_strict_phrase_match_skips_the_llm():
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)

    mode, confident = await _detect_switch_intent("can you tell me a story", conversation, current_mode="1")

    assert mode == "2"
    assert confident is True  # decision 0046: strict match -> no confirmation needed
    assert llm.calls == []  # strict phrase match never reaches classify_intent()


async def test_detect_switch_intent_no_activity_keyword_skips_the_llm():
    """The core cost-control property: an ordinary turn that never
    mentions an activity never pays for an extra LLM call."""
    llm = _FakeLLM(reply="STORY")
    conversation = ConversationService(llm)

    mode, confident = await _detect_switch_intent("the cat has four legs", conversation, current_mode="1")

    assert mode is None
    assert confident is False
    assert llm.calls == []


async def test_detect_switch_intent_ambiguous_phrasing_falls_back_to_the_llm():
    llm = _FakeLLM(reply="SONG")
    conversation = ConversationService(llm)

    mode, confident = await _detect_switch_intent(
        "I don't want a story, let's do something else musical", conversation, current_mode="1"
    )

    assert mode == "4"
    assert confident is False  # decision 0046: LLM-fallback match -> caller must confirm
    assert len(llm.calls) == 1


async def test_detect_switch_intent_llm_none_keeps_current_mode():
    llm = _FakeLLM(reply="NONE")
    conversation = ConversationService(llm)

    mode, confident = await _detect_switch_intent(
        "can we sing something later maybe", conversation, current_mode="1"
    )

    assert mode is None
    assert confident is False


async def test_detect_switch_intent_matching_current_mode_is_a_no_op():
    """The actual bug fix: found live -- "I want to teach you
    mathematics" said *while already in Teachable-Friend mode*
    matched the TEACH intent (correctly) but, with no check against
    the mode already running, was treated as a "switch" to the mode
    already active, restarting it on every single teaching statement
    instead of ever continuing the conversation. Detecting the mode
    you're already in must be a no-op."""
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)

    mode, confident = await _detect_switch_intent(
        "I want to teach you mathematics, I want to be the teacher",
        conversation,
        current_mode="1",  # already in Teachable-Friend -- the strict phrase matches TEACH -> "1"
    )

    assert mode is None
    assert confident is False
    assert llm.calls == []  # the strict phrase still matched; only the mode-equality check changed


async def test_detect_switch_intent_llm_fallback_matching_current_mode_is_also_a_no_op():
    """Same suppression, but via the LLM-fallback tier instead of the
    strict phrase tier -- a phrasing that doesn't match the strict
    TEACH regex but still mentions "teach" while already in
    Teachable-Friend mode must not restart it either."""
    llm = _FakeLLM(reply="TEACH")
    conversation = ConversationService(llm)

    mode, confident = await _detect_switch_intent(
        "can we keep going with the teaching", conversation, current_mode="1"
    )

    assert mode is None
    assert confident is False
    assert len(llm.calls) == 1  # the LLM fallback was still called -- just suppressed after


# -- _confirm_switch (decision 0046) ---------------------------------------


async def test_confirm_switch_speaks_the_mode_specific_prompt_and_returns_true_on_yes():
    tts = _FakeTTS()
    face = _FakeFace()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        return_value="yes",
    ):
        confirmed = await _confirm_switch("2", tts, _FakeAudio(), "fake-stt", face, 1.0)

    assert confirmed is True
    # Decision 0046 addendum: the confirmation prompt, then a short
    # acknowledgment of the answer -- the answer itself must never be
    # silently consumed with no response at all.
    assert tts.synthesized == [
        "Sounds like you want to hear a story -- is that right?",
        "Great, let's do that!",
    ]


async def test_confirm_switch_returns_false_on_no():
    tts = _FakeTTS()
    face = _FakeFace()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        return_value="no thanks",
    ):
        confirmed = await _confirm_switch("4", tts, _FakeAudio(), "fake-stt", face, 1.0)

    assert confirmed is False


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
        next_mode, carried_text = await _run_teachable_friend(
            conversation, _FakeTTS(), _FakeAudio(), "fake-stt",
            memories, engagement, transcripts, face, "child-1", 1.0,
        )

    assert next_mode == "2"
    # Decision 0042 addendum: the triggering utterance is carried
    # forward instead of being silently discarded, so the next mode
    # can reply to it as a real turn rather than making the child
    # repeat themselves.
    assert carried_text == "tell me a story please"
    assert len(llm.calls) == 1  # only the first, ordinary turn reached teachable_friend_reply()
    assert len(engagement.list_for_child("child-1")) == 1  # finally cleanup still ran
    assert len(transcripts.list_for_child("child-1")) == 1


async def test_carried_over_text_gets_a_real_reply_without_another_capture():
    """The actual bug fix: the mode being switched into must reply to
    the triggering utterance as a genuine first turn, not silently
    wait for a fresh capture -- found live, the child had to repeat
    themselves every time a switch happened."""
    conn = connect(":memory:")
    memories = MemoryRepository(conn)
    engagement = EngagementRepository(conn)
    transcripts = TranscriptRepository(conn)
    llm = _FakeLLM(reply="Sure, let's just chat! What's on your mind?")
    summarizer = _FakeLLM(reply="NOTHING")
    conversation = ConversationService(llm, summarizer_llm=summarizer)
    face = _FakeFace()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=AssertionError("must not capture fresh input for the carried-over turn"),
    ):
        # Ctrl-C after the first (carried-over) turn is processed --
        # proves that turn used initial_text, since _capture_and_transcribe
        # would raise immediately if it were ever called.
        with patch(
            "companion_robot.voice_loop_demo._speak",
            new_callable=AsyncMock,
            side_effect=KeyboardInterrupt,
        ):
            try:
                await _run_everyday_companion(
                    conversation, _FakeTTS(), _FakeAudio(), "fake-stt",
                    memories, engagement, transcripts, face, "child-1", 1.0,
                    initial_text="let's just chat",
                )
            except KeyboardInterrupt:
                pass

    assert len(llm.calls) == 1
    # The fake stores a reference to the function's own `messages` list,
    # which gets the assistant reply appended after the call -- check
    # the first entry (the carried-over turn) rather than the whole list.
    assert llm.calls[0][0][0] == {"role": "user", "content": "let's just chat"}


async def test_fallback_tier_switch_declined_stays_in_current_mode():
    """Decision 0046: an LLM-fallback-tier detection ("can we keep
    going with the teaching" mentions "teach" but doesn't match the
    strict TEACH phrase) must ask before switching. Declining must not
    switch at all -- the original utterance gets a normal reply in the
    mode it was actually said in."""
    conn = connect(":memory:")
    memories = MemoryRepository(conn)
    engagement = EngagementRepository(conn)
    transcripts = TranscriptRepository(conn)
    # First call: ConversationService.classify_intent() (the fallback
    # tier) -- returns TEACH. Second call: everyday_companion_reply(),
    # since the switch gets declined and the turn continues normally.
    llm = _FakeLLM(reply="irrelevant -- overridden per-call below")
    llm.generate_reply = AsyncMock(
        side_effect=[("TEACH", "fake-model"), ("Sure, let's keep chatting!", "fake-model")]
    )
    summarizer = _FakeLLM(reply="NOTHING")
    conversation = ConversationService(llm, summarizer_llm=summarizer)
    face = _FakeFace()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=[
            "can we keep going with the teaching",  # fallback-tier TEACH match
            "no",  # declines the confirmation
        ],
        # A third call would mean the loop looped back around to listen
        # again instead of falling through to a normal reply -- raise to
        # catch that instead of hanging the test.
    ):
        with patch(
            "companion_robot.voice_loop_demo._speak",
            new_callable=AsyncMock,
            # confirmation prompt, decline acknowledgment, then the real reply
            side_effect=[None, None, KeyboardInterrupt],
        ):
            try:
                await _run_everyday_companion(
                    conversation, _FakeTTS(), _FakeAudio(), "fake-stt",
                    memories, engagement, transcripts, face, "child-1", 1.0,
                )
            except KeyboardInterrupt:
                pass

    assert llm.generate_reply.call_count == 2
    # The declined turn still got a real reply in the same mode.
    assert llm.generate_reply.call_args_list[1].args[0][0] == {
        "role": "user",
        "content": "can we keep going with the teaching",
    }
