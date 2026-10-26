"""Unit tests for decision 0042's hybrid intent detection and voice
picker in voice_loop_demo.py -- real ConversationService/repositories,
fake LLM/tts/audio/stt stand-ins, no real API calls, hardware, or
keyboard input() needed.
"""
import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from companion_robot.conversation.service import ConversationService
from companion_robot.device.interfaces import DeviceState
from companion_robot.engagement.repository import EngagementRepository
from companion_robot.engagement.schema import EngagementMode
from companion_robot.memory.repository import MemoryRepository
from companion_robot.parent_controls.reading_exercises import (
    ReadingExerciseRecord,
    ReadingExerciseRepository,
)
from companion_robot.reading.repository import ReadingRepository
from companion_robot.reading.schema import GraphemeMastery, Miscue, ReadingProfile
from companion_robot.reading.word_timing import WordTiming
from companion_robot.reading.word_game import _CLOSING_LINES, blank_vowels
from companion_robot.storage.sqlite import connect
from companion_robot.transcripts.repository import TranscriptRepository
from companion_robot.voice.interfaces import LanguageModelBackend
import companion_robot.voice_loop_demo as voice_loop_demo
from companion_robot.voice_loop_demo import (
    _MAX_FULL_CORRECTIONS,
    _THINKING_FILLERS,
    _classify_read_first_offer_reply,
    _classify_reread_reply,
    _confirm_switch,
    _detect_switch_intent,
    _generate_with_thinking_filler,
    _give_brief_callout,
    _pick_item_by_voice,
    _resolve_spoken_choice,
    _run_everyday_companion,
    _run_reading_partner,
    _run_teachable_friend,
    _run_word_family_practice,
    _speak_with_word_highlight,
    _speak_while_thinking,
    _weakest_mastery_for_miscues,
)


@pytest.fixture(autouse=True)
def _reading_exercises_enabled(monkeypatch):
    """Decision 0069: parent-uploaded exercises default to enabled now
    (CHITTI_ENABLE_READING_EXERCISES=0 opts out), so this explicit
    setenv("1") is redundant against today's real default -- kept
    anyway so these tests stay correct even if that default ever
    changes again, and so they read the same regardless. Most Reading
    Partner tests in this file use a pending exercise purely as a
    convenient, deterministic content fixture -- not to test the
    exercise feature itself; test_run_reading_partner_exercise_is_*/
    ..._uses_a_pending_exercise_with_the_flag_unset are the places that
    explicitly assert the flag's own on/off behavior, overriding this
    fixture.
    """
    monkeypatch.setenv("CHITTI_ENABLE_READING_EXERCISES", "1")


class _FakeLLM(LanguageModelBackend):
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[list[dict], str]] = []

    async def generate_reply(self, messages, system_prompt):
        self.calls.append((messages, system_prompt))
        return self.reply, "fake-model"


class _FakeAudio:
    def __init__(self) -> None:
        self.played: list[bytes] = []

    async def play(self, audio_bytes: bytes) -> None:
        self.played.append(audio_bytes)

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
        self.reading_texts: list[list[str] | None] = []
        self.spotlights: list[str | None] = []
        self.word_grids: list[list[str] | None] = []
        self.word_grid_highlights: list[str | None] = []
        self.reading_text_highlights: list[str | None] = []
        self.reading_text_highlight_sets: list[set[tuple[int, int]] | None] = []
        # Decision 0090: the three display-state setters below are
        # recorded into this one shared, real-call-order log too (as
        # well as their own per-method lists above, which most
        # existing tests already rely on) -- the render loop only ever
        # draws ONE of spotlight/word_grid/reading_text at a time
        # (whichever is non-None, checked in that priority order), so
        # a test that cares which one actually showed on screen at a
        # given moment needs their real interleaving, not each one's
        # own separately-indexed list.
        self.display_calls: list[tuple[str, object]] = []

    def set_status_led(self, state: DeviceState) -> None:
        self.states.append(state)

    def set_expression_mode(self, mode: str | None) -> None:
        self.modes.append(mode)

    def set_reading_text(
        self, lines: list[str] | None, *, wpm: float = 45.0, font_size: int = 28,
        font_color: str = "white",
    ) -> None:
        self.reading_texts.append(lines)
        self.display_calls.append(("reading_text", lines))

    def set_reading_spotlight(self, word: str | None) -> None:
        self.spotlights.append(word)
        self.display_calls.append(("spotlight", word))

    def set_word_grid(self, words: list[str] | None) -> None:
        self.word_grids.append(words)
        self.display_calls.append(("word_grid", words))

    def set_word_grid_highlight(self, word: str | None) -> None:
        self.word_grid_highlights.append(word)

    def set_reading_text_highlight(
        self, word: str | None, sentence_index: int | None, word_position: int | None = None,
    ) -> None:
        self.reading_text_highlights.append((sentence_index, word_position, word))

    def set_reading_text_highlights(self, positions: set[tuple[int, int]] | None) -> None:
        self.reading_text_highlight_sets.append(positions)


@contextlib.contextmanager
def _patch_captures(*side_effect):
    """Patches _capture_and_transcribe() with one ordered side_effect
    list. (Decisions 0084-0086 briefly routed some captures through a
    second function, _capture_and_transcribe_after_beep() -- decision
    0087 removed it after real-hardware testing, so this only ever
    patches the one capture function again; kept as a helper since so
    many tests below already call it this way.)"""
    mock = AsyncMock(side_effect=list(side_effect))
    with patch("companion_robot.voice_loop_demo._capture_and_transcribe", mock):
        yield mock


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


async def test_detect_switch_intent_chat_via_llm_fallback_is_always_confident():
    """Decision 0048: switching into Just Chat never needs a spoken
    confirmation, even via the lower-confidence LLM-fallback tier --
    found live that confirming right after an emotional statement
    ("my friend isn't talking to me") read as Chitti not listening.
    Landing in Just Chat by mistake costs nothing, unlike Story/Song/
    Teach, so this is the one mode where "confident" is always True."""
    llm = _FakeLLM(reply="CHAT")
    conversation = ConversationService(llm)

    mode, confident = await _detect_switch_intent(
        "my friend is not talking to me", conversation, current_mode="1"
    )

    assert mode == "3"
    assert confident is True
    assert len(llm.calls) == 1  # the fallback tier still ran -- only confirmation is skipped


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


# -- _speak_while_thinking / _generate_with_thinking_filler (decision 0050) -


class _FakeTask:
    """Reports done() as False for the first `done_after` checks, then
    True -- lets the escalation-stopping logic be tested precisely
    without depending on real asyncio scheduling timing (genuinely
    fragile to get right: nothing in a chain of trivial fake
    coroutines actually yields to the event loop the way real network
    I/O does, so a real asyncio.Task's completion timing relative to
    the filler loop isn't reliably controllable here)."""

    def __init__(self, done_after: int) -> None:
        self._checks = 0
        self._done_after = done_after

    def done(self) -> bool:
        self._checks += 1
        return self._checks > self._done_after


async def test_speak_while_thinking_stops_once_the_task_is_done():
    tts = _FakeTTS()
    face = _FakeFace()
    fake_task = _FakeTask(done_after=1)  # "done" starting from the 2nd check

    await _speak_while_thinking(fake_task, tts, _FakeAudio(), face, 1.0)

    # Decision 0117: which filler is picked first is now random (so a
    # session's many short waits don't all start with the exact same
    # line) -- just the one real filler, from the real pool.
    assert len(tts.synthesized) == 1
    assert tts.synthesized[0] in _THINKING_FILLERS


async def test_speak_while_thinking_never_speaks_more_than_one_filler():
    """Decision 0121, found live: a genuinely slow call used to
    escalate through up to 3 filler lines back-to-back, which read as
    stalling. A Future that's never resolved guarantees task.done()
    stays False for as long as this runs -- proves the function
    speaks exactly one filler and then stops, rather than looping."""
    tts = _FakeTTS()
    face = _FakeFace()
    never_done = asyncio.get_running_loop().create_future()

    await _speak_while_thinking(never_done, tts, _FakeAudio(), face, 1.0)

    assert len(tts.synthesized) == 1
    assert tts.synthesized[0] in _THINKING_FILLERS


async def test_speak_while_thinking_varies_which_filler_comes_first():
    """Decision 0117, found live: this used to always start with the
    exact same line ("Hmm, let me think about that...") on every
    single call -- across a session with many LLM waits, the child
    heard that same opening line over and over. Across enough calls,
    the first filler spoken should vary, not always be the same one."""
    first_fillers = set()
    for _ in range(20):
        tts = _FakeTTS()
        face = _FakeFace()
        fake_task = _FakeTask(done_after=1)
        await _speak_while_thinking(fake_task, tts, _FakeAudio(), face, 1.0)
        first_fillers.add(tts.synthesized[0])

    assert len(first_fillers) > 1


async def test_generate_with_thinking_filler_returns_the_real_result():
    tts = _FakeTTS()
    face = _FakeFace()

    async def _coro():
        return "the real answer"

    result = await _generate_with_thinking_filler(_coro(), tts, _FakeAudio(), face, 1.0, "test_label")

    assert result == "the real answer"


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


async def test_run_teachable_friend_switches_to_just_chat_with_no_confirmation():
    """Decision 0048, the actual product fix: an emotional statement
    ("my friend is not talking to me") said in Teachable-Friend that
    resolves to CHAT via the LLM-fallback tier must switch straight
    into Just Chat -- no "is that right?" confirmation question -- so
    the carried-over text gets a real empathetic reply as its very
    next turn, immediately."""
    conn = connect(":memory:")
    memories = MemoryRepository(conn)
    engagement = EngagementRepository(conn)
    transcripts = TranscriptRepository(conn)
    # Only one scripted reply: classify_intent() (fallback tier) --
    # CHAT. If _confirm_switch() asked a question, generate_reply
    # would never be called again for it (it's deterministic, not an
    # LLM call), but tts.synthesized below is what actually proves no
    # question was spoken.
    llm = _FakeLLM(reply="CHAT")
    summarizer = _FakeLLM(reply="NOTHING")
    conversation = ConversationService(llm, summarizer_llm=summarizer)
    face = _FakeFace()
    tts = _FakeTTS()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        return_value="my friend is not talking to me",
    ):
        next_mode, carried_text = await _run_teachable_friend(
            conversation, tts, _FakeAudio(), "fake-stt",
            memories, engagement, transcripts, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert carried_text == "my friend is not talking to me"
    assert len(llm.calls) == 1  # only classify_intent() ran -- never reached a reply call
    assert tts.synthesized == []  # no confirmation prompt was ever spoken


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
        # would raise immediately if it were ever called. Decision
        # 0121: exactly one thinking filler plays before the real
        # reply's own _speak call now (down from up to three).
        with patch(
            "companion_robot.voice_loop_demo._speak",
            new_callable=AsyncMock,
            side_effect=[None, KeyboardInterrupt],
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
            # confirmation prompt, decline acknowledgment, decision
            # 0121's one thinking filler, then the real reply
            side_effect=[None, None, None, KeyboardInterrupt],
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


# -- _run_reading_partner (decision 0051) ----------------------------------


async def test_run_reading_partner_never_checks_the_read_aloud_transcript_for_a_switch():
    """The mode's one genuinely different rule, called out explicitly
    in its own docstring: intent-switch detection must run on the
    short "want another one?" reply between books, never on the
    child's read-aloud transcript -- that transcript *is* the story's
    own text, so running phrase detection on it would be a false-
    positive source. The read-aloud text below ("tell me a story")
    would itself resolve to a strict-phrase STORY match if it were
    (incorrectly) checked -- if that happened, the loop would break
    after the FIRST capture and the second, real "what next" turn
    would never be reached."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    llm = _FakeLLM(reply="TITLE: The Cat\nPAGE: A cat sat.\nPAGE: A cat ran.")
    conversation = ConversationService(llm)
    face = _FakeFace()

    # A function, not a static list: the read-aloud text ("tell me a
    # story") is totally unrelated to the generated book, so decision
    # 0052's hint-and-retry loop will very likely fire for a missed
    # word before the real "what next" turn is ever reached -- every
    # call after the first (whichever turn it ends up being) returns
    # the same switch phrase, so the test doesn't need to predict
    # exactly how many hint-stage captures happen in between.
    calls = {"n": 0}

    async def _capture_side_effect(*_args, **_kwargs):
        calls["n"] += 1
        return "tell me a story" if calls["n"] == 1 else "can we sing a song"

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=_capture_side_effect,
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, _FakeTTS(), _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    # Only the real "what next" turn ("can we sing a song") decided the
    # switch -- had the read-aloud transcript been checked instead, this
    # would be STORY ("2") and the loop would have stopped after one capture.
    assert next_mode == "4"
    assert carried_text == "can we sing a song"


async def test_run_reading_partner_grades_the_read_and_persists_mastery():
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    llm = _FakeLLM(reply="TITLE: The Cat\nPAGE: A cat sat.\nPAGE: A cat ran.")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        # Decision 0095: the child reads the WHOLE story in one take
        # now, not one capture per sentence -- "a cat sat a cat ran"
        # is a perfect read of both sentences at once, so no sentence
        # gets flagged and decision 0052's hint ladder never fires.
        # Decision 0094: Chitti's "read it to you first?" offer is
        # asked once per call -- "no thanks" declines it. "no thanks"
        # also declines decision 0057's post-reading word game
        # (offered since "cat"/"sat"/"ran" all qualify) so it never
        # consumes further captures either. The final turn is a
        # genuine switch request (needed so the mode loop -- which
        # otherwise keeps generating books forever -- actually
        # terminates for this test).
        "no thanks", "a cat sat a cat ran", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert carried_text == "let's just chat"
    # A perfect read-aloud got a warm, qualitative spoken feedback line.
    assert any("really well" in line for line in tts.synthesized)
    # Found live: nothing used to tell the child Chitti was waiting on
    # them after the feedback -- it just silently started listening.
    assert any("try another one" in line for line in tts.synthesized)
    # Decision 0093: the whole story is shown at once, set before the
    # per-sentence loop starts. Decision 0112: no longer cleared once
    # the passage itself is done (the child needs to keep seeing it
    # through comprehension questions/the word game) -- only cleared
    # once the mode loop actually exits (the `finally`).
    assert face.reading_texts[0] == ["A cat sat.", "A cat ran."]
    assert None in face.reading_texts
    # The session was actually persisted, not just held in memory.
    profile = reading.get_or_create("child-1")
    assert profile.sessions_completed == 1


async def test_run_reading_partner_uses_a_pending_exercise_instead_of_generating():
    """Decision 0052: a parent-assigned exercise is read verbatim --
    no book-generation LLM call at all -- and marked consumed so it's
    not served again next session. Decision 0059 does still call the
    LLM for this exercise, but only to generate comprehension
    questions about it, never to generate or rewrite the passage
    itself -- the two calls are distinguished by their own prompts."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="The cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    # No "QUESTION:" lines in this reply -- generate_comprehension_questions()
    # parses it to an empty list, so decision 0059's phase is a no-op here.
    llm = _FakeLLM(reply="unused -- must never be a book-generation call")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        # Decision 0085: the sentence's capture is preceded by
        # Chitti's own "read it to you first?" offer -- "no thanks"
        # declines it. Also declines decision 0057's post-reading
        # word game.
        "no thanks", "the cat sat", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # No book-generation call -- the exercise was used as-is.
    assert not any(
        call[0][0]["content"] == "Write the story now." for call in llm.calls
    )
    assert face.reading_texts[0] == ["The cat sat."]
    exercise = reading_exercises.list_for_child("child-1")[0]
    assert exercise.consumed_at is not None


async def test_run_reading_partner_uses_a_pending_exercise_with_the_flag_unset(monkeypatch):
    """Decision 0069 (superseding 0063): with CHITTI_ENABLE_READING_EXERCISES
    unset -- the real default now -- a pending exercise IS used, not
    ignored. Found live: a parent-uploaded passage sat unused while
    this flag defaulted off, and when LLM generation then failed, the
    child was left with nothing even though real material existed."""
    monkeypatch.delenv("CHITTI_ENABLE_READING_EXERCISES", raising=False)
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="The cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused -- must never be a book-generation call")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures("no thanks", "the cat sat", "no thanks", "let's just chat"):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert face.reading_texts[0] == ["The cat sat."]  # the exercise, not an LLM-generated book
    exercise = reading_exercises.list_for_child("child-1")[0]
    assert exercise.consumed_at is not None


async def test_run_reading_partner_exercise_is_ignored_when_flag_explicitly_off(monkeypatch):
    """CHITTI_ENABLE_READING_EXERCISES=0 is still a real opt-out --
    a pending exercise must be completely ignored (never read, never
    consumed) and every book comes from the LLM path instead."""
    monkeypatch.setenv("CHITTI_ENABLE_READING_EXERCISES", "0")
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="The cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="TITLE: The Dog\nPAGE: A dog ran.")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures("no thanks", "a dog ran", "no thanks", "let's just chat"):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert face.reading_texts[0] == ["A dog ran."]  # the LLM-generated book, not the exercise
    exercise = reading_exercises.list_for_child("child-1")[0]
    assert exercise.consumed_at is None  # never touched


async def test_run_reading_partner_feedback_cites_a_specific_word_from_the_read():
    """Decision 0055: a clean read with no hint cites a real standout
    word from the actual passage, not a list of phonics sound labels."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A little bunny hops.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        # Decision 0085: the sentence's own "read it to you first?"
        # offer, declined. "no thanks" also declines decision 0057's
        # post-reading word game.
        "no thanks", "a little bunny hops", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert any('"little"' in line for line in tts.synthesized)  # the longest word read


async def test_run_reading_partner_hint_retry_succeeds():
    """Decision 0116: a missed word is re-exposed slow/medium/fast
    (no more graduated phonics hint ladder), then checked once -- a
    correct retry gets simple praise."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        # Decision 0085: the sentence's own "read it to you first?"
        # offer, declined, before the read-aloud itself. "mat" for
        # "sat" is a clean substitution (test_reading_alignment's own
        # precedent); the retry gets it right. Decision 0074: a
        # resolved word still means the sentence gets reread once
        # ("sat" again). "no thanks" declines decision 0057's
        # post-reading word game.
        "no thanks", "a cat mat", "sat", "a cat sat", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # [0] story intro, [1] the "read it to you first?" offer, [2] the
    # "give it a try" turn cue, [3] decision 0095's "let's work on
    # this one" attention intro, [4] decision 0098's own highlighted
    # read of the flagged sentence itself, [5]-[7] the missed word
    # itself spoken three times (slow/medium/fast -- decision 0116),
    # [8] simple praise for the correct retry.
    assert tts.synthesized[5:8] == ["sat", "sat", "sat"]
    assert tts.synthesized[8] == "There you go!"
    # Not asserted by fixed index from here on -- decision 0074's
    # reread/word-meaning-check step runs a real LLM call wrapped in
    # decision 0050's thinking-filler, whose line count depends on
    # timing, not just content.
    assert any(
        line.startswith("Good try! Reading can be tricky sometimes.")
        for line in tts.synthesized
    )
    # Decision 0116: the retry is an echo (the child heard the word
    # said in full three times right before attempting it) -- it no
    # longer feeds mastery evidence the way the old graduated hint
    # ladder's own early stages did. Only the original cold-read miss
    # counts.
    profile = reading.get_or_create("child-1")
    assert profile.masteries["s"].opportunities == 1
    # Decision 0053: the actual bug fix -- the display froze on the
    # missed word for the whole exchange, then cleared once it ended,
    # rather than leaving the child with no idea what was being
    # asked. Decision 0113: now a highlight within the full story
    # (still on screen the whole time), not an isolated spotlight
    # view -- "sat" is story word index 2 ("A cat sat.").
    assert face.reading_text_highlights == [(0, 2, "sat"), (0, None, None)]


async def test_run_reading_partner_hint_retry_continues_without_penalty_when_still_wrong():
    """Decision 0116: even if the child still doesn't get the missed
    word right after hearing it slow/medium/fast, the session
    continues to normal feedback -- no penalty, no infinite loop (and
    no more graduated escalation -- one exposure, one check)."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    # Decision 0085: the sentence's own "read it to you first?" offer,
    # declined, before the read-aloud itself. Decision 0084: a still-
    # wrong word still triggers a reread -- modeled by Chitti first.
    # "no thanks" declines decision 0057's post-reading word game.
    with _patch_captures(
        "no thanks", "a cat mat", "nope", "a cat mat", "still nope",
        "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # [0] story intro, [1] the "read it to you first?" offer, [2] the
    # "give it a try" turn cue, [3] decision 0095's "let's work on
    # this one" attention intro, [4] decision 0098's own highlighted
    # read of the flagged sentence itself, [5]-[7] the missed word
    # spoken three times (slow/medium/fast -- decision 0116), [8] the
    # gentle reveal since the retry was still wrong.
    assert tts.synthesized[5:8] == ["sat", "sat", "sat"]
    assert tts.synthesized[8] == 'That\'s okay! The word is "sat". Let\'s keep going!'
    assert "There you go!" not in tts.synthesized
    # Decision 0084: a still-wrong word still gets the model-then-
    # repeat flow instead of a blanket "Nice reading!" below. Not
    # asserted by fixed index -- the word-meaning check in between
    # runs a real LLM call wrapped in decision 0050's thinking-filler,
    # whose line count depends on timing, not just content.
    assert "I'll read it for you first. Listen:" in tts.synthesized
    assert "Now it's your turn! Give it a try." in tts.synthesized
    # Decision 0081: the reread still had "mat" for "sat" -- a short
    # correction cycle runs instead of blanket praise, and since the
    # correction attempt is wrong too, it closes with "the word is...",
    # never "Nice reading!" for this unresolved sentence.
    assert "Let's look at this word again. Listen: sat." in tts.synthesized
    assert 'Good try! The word is "sat".' in tts.synthesized
    assert "Nice reading!" not in tts.synthesized
    feedback_line = next(
        line for line in tts.synthesized if line.startswith("Good try! Reading can be tricky")
    )
    # Decision 0055: an unresolved word is mentioned again in the
    # final feedback as something to revisit.
    assert '"sat"' in feedback_line
    # Decision 0053: the display stayed frozen (highlighted, within
    # the full story -- decision 0113) on the missed word for the
    # whole exposure-and-check exchange, then cleared. Decision 0081:
    # the reread's own correction cycle highlights "sat" again (then
    # clears it) on top of that original highlight -- "sat" is story
    # word index 2 ("A cat sat.").
    assert face.reading_text_highlights == [
        (0, 2, "sat"), (0, None, None), (0, 2, "sat"), (0, None, None),
    ]


async def test_run_reading_partner_handles_every_real_miss_not_just_the_first():
    """Decision 0065/0116: a read with two real misses gets both
    re-exposed (slow/medium/fast) and checked in turn, not just the
    first -- one gets it right, the other doesn't, independently."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="little garden hops.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # decision 0085: declines Chitti's "read it to you first?" offer
        "silly gotten hops",  # the read-aloud -- "little" and "garden" both missed
        "little",  # "little" resolved
        "nope",  # "garden" still wrong
        "little garden hops",  # decision 0074/0084: the sentence reread after retrying
        "no thanks",  # declines the word game
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # Both missed words got their own slow/medium/fast exposure,
    # "little" first (reading order).
    assert tts.synthesized.count("little") >= 3
    assert "There you go!" in tts.synthesized  # "little" resolved
    assert tts.synthesized.count("garden") >= 3
    assert 'That\'s okay! The word is "garden". Let\'s keep going!' in tts.synthesized
    # "little" is excluded from the final practice-words mention
    # (resolved live); "garden" still surfaces since it never was.
    feedback_line = next(
        line for line in tts.synthesized if line.startswith("Good try!")
    )
    assert '"garden"' in feedback_line
    assert '"little"' not in feedback_line


async def test_run_reading_partner_word_family_offered_after_independent_resolution():
    """Decision 0066: a word resolved via an EARLIER hint stage (real
    decoding, not an echo) triggers an offer to practice a same-rime
    word family; accepting reads through every verified candidate."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="WORD: cat\nWORD: bat")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # decision 0085: declines Chitti's "read it to you first?" offer
        "a cat mat",  # read-aloud -- "sat" substituted as "mat"
        "sat",  # resolved on the very first retry -- real decoding
        "yes",  # accepts the word-family offer
        "cat bat",  # decision 0084: reads every family word in one take
        "a cat sat",  # decision 0074/0084: the sentence reread after hint practice
        "no thanks",  # declines the separate post-reading word game
        "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert any('"sat"' in line and "more words" in line for line in tts.synthesized)
    # Decision 0084: both candidates shown together as one grid, read
    # in a single capture -- not asked (or captured) one at a time.
    assert ["cat", "bat"] in face.word_grids
    assert None in face.word_grids  # cleared after the one capture
    assert "Can you read all of these words for me?" in tts.synthesized
    # Decision 0096: both words correct from one capture gets one
    # combined line, not one "Yes!"/"You got it!" per word in a row
    # with no child input in between.
    assert "Wow, you read all of them: cat, bat! Great job!" in tts.synthesized
    # Decision 0090, found live: the hint ladder's own spotlight for
    # "sat" was still showing when the grid was set -- the render
    # loop draws the spotlight over the grid whenever both are set,
    # so the grid never actually appeared. The spotlight's own
    # clearing call must come before the grid is set, in real call
    # order (not just "somewhere in each list"), or the fix doesn't
    # actually help.
    grid_call = ("word_grid", ["cat", "bat"])
    grid_index = face.display_calls.index(grid_call)
    assert ("spotlight", None) in face.display_calls[:grid_index]


async def test_run_reading_partner_word_family_gives_one_reply_when_nothing_was_attempted():
    """Decision 0089, found live: a reply that doesn't attempt any of
    the words at all ("I don't know") used to still react to all four
    candidates individually, each with its own full phonics breakdown
    and TTS round trip -- felt like it would never end. One short,
    combined line instead, not four."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="WORD: hat\nWORD: cat\nWORD: bat\nWORD: mat")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",
        "a cat mat",
        "sat",
        "yes",
        "I don't know",  # decision 0089: no family word attempted at all
        "a cat sat",
        "no thanks",
        "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "That's okay! Those words were hat, cat, bat, mat. Let's keep going!" in tts.synthesized
    # Not one individual phonics-breakdown reaction per word.
    assert not any(line.startswith('Good try! The word is "') for line in tts.synthesized)


async def test_run_reading_partner_word_family_skipped_when_llm_gives_no_usable_words():
    """A reply with no verifiable WORD: candidates degrades to simply
    skipping the activity -- no offer spoken, no extra capture."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks", "a cat mat", "sat", "a cat sat", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert not any("more words like it" in line for line in tts.synthesized)


async def test_run_reading_partner_word_family_offered_at_most_once_per_sentence():
    """Decision 0079, found live: a sentence with several real misses
    that each resolve independently (e.g. "cat" AND "sat") used to
    trigger a SEPARATE word-family detour for every single one --
    stacking up before the sentence was even done. Capped at one per
    sentence now; the first word to resolve still gets the offer."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="WORD: hat\nWORD: bat\nWORD: rat\nWORD: mat")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # decision 0085: declines Chitti's "read it to you first?" offer
        "a dog ran",  # read-aloud -- both "cat" and "sat" substituted
        "cat",  # resolves "cat" on the very first retry
        "no",  # declines the word-family offer for "cat"
        "sat",  # resolves "sat" on the very first retry too
        "a cat sat",  # decision 0074/0084: the sentence reread
        "no thanks",  # declines the separate post-reading word game
        "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    offers = [line for line in tts.synthesized if "more words like it" in line]
    assert len(offers) == 1


async def test_word_family_practice_highlights_each_word_while_modeling_it():
    """Decision 0095: when read_first is True, Chitti models every
    word in the family before asking the child to read them -- each
    word gets highlighted in the grid while it's actually being
    spoken, not just shown statically throughout, and the highlight
    clears once modeling is done."""
    llm = _FakeLLM(reply="WORD: cat\nWORD: bat")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures("yes", "cat bat"):
        await _run_word_family_practice(
            "sat", conversation, tts, _FakeAudio(), "fake-stt", face, 1.0, 6,
            ["short_vowels"], read_first=True,
        )

    assert face.word_grid_highlights == ["cat", "bat", None]


async def test_word_family_practice_models_each_word_with_its_own_tts_call_even_with_timestamps():
    """Decision 0102 originally combined the whole family into one
    TTS call ("cat. bat."), re-transcribed via Whisper to sync the
    grid highlight word-by-word, whenever the STT backend supported
    timestamps. Decision 0114, found live: for a fast string of short
    rhyming words, Whisper's own re-transcription routinely didn't
    produce one timing per word, leaving most of them never clearly
    spoken or highlighted. Always uses one TTS call per word now --
    reliable, trivially synced -- regardless of what the STT backend
    can do; the "with timestamps available" STT fake is used here to
    prove that doesn't change this path's behavior any more."""
    llm = _FakeLLM(reply="WORD: cat\nWORD: bat")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()
    stt = _FakeSTTWithTimestamps(
        [WordTiming(word="cat", start=0.0, end=0.01), WordTiming(word="bat", start=0.01, end=0.02)]
    )

    with _patch_captures("yes", "cat bat"):
        await _run_word_family_practice(
            "sat", conversation, tts, _FakeAudio(), stt, face, 1.0, 6,
            ["short_vowels"], read_first=True,
        )

    assert "cat. bat." not in tts.synthesized
    # One separate call per word instead.
    assert "cat" in tts.synthesized
    assert "bat" in tts.synthesized
    assert face.word_grid_highlights == ["cat", "bat", None]


async def test_word_family_practice_only_corrects_the_missed_word_not_every_word():
    """Decision 0096, found live: all words correct from one capture
    used to get a separate "Yes!"/"You got it!" line each, read back
    in a row with no child input in between -- felt robotic. A
    partial miss should name what was right once, then work only on
    the word actually missed, not re-praise the ones already right."""
    llm = _FakeLLM(reply="WORD: cat\nWORD: bat")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()
    audio = _FakeAudio()

    with _patch_captures("yes", "cat"):  # "bat" never attempted
        await _run_word_family_practice(
            "sat", conversation, tts, audio, "fake-stt", face, 1.0, 6,
            ["short_vowels"],
        )

    assert "Nice! You got cat." in tts.synthesized
    # Decision 0120: no more phonics breakdown here either -- just
    # names the real word, same simplified style decisions 0116/0118
    # already established everywhere else in the reading flow.
    assert 'That\'s okay! The word is "bat". Let\'s keep going!' in tts.synthesized
    assert not any("like in" in line for line in tts.synthesized)
    # No real recorded phonics clip plays for the missed word either --
    # _FakeTTS.synthesize()'s fixed b"fake-audio" placeholder is the
    # only thing ever played now.
    assert all(clip == b"fake-audio" for clip in audio.played)
    # Found live: nothing showed "bat" on screen during its own
    # correction -- the grid was already cleared, so the screen just
    # fell back to whatever was on it before. Spotlighted instead,
    # then cleared once the correction is done.
    # [0] is decision 0090's own clear of the hint ladder's leftover
    # spotlight before the grid is shown; [1]/[2] are this fix's own
    # spotlight-then-clear around "bat"'s correction.
    assert face.spotlights == [None, "bat", None]


class _FakeSTTWithTimestamps:
    """Decision 0098: a fake STT backend that also supports the
    additive transcribe_with_word_timestamps() capability -- most
    fakes in this file (just "fake-stt", the bare string) deliberately
    don't, exercising _speak_with_word_highlight()'s graceful
    degradation to a plain, unhighlighted speak()."""

    def __init__(self, timings: list[WordTiming]) -> None:
        self._timings = timings
        self.timestamp_calls = 0

    async def transcribe_with_word_timestamps(self, audio_bytes: bytes) -> list[WordTiming]:
        self.timestamp_calls += 1
        return self._timings


class _FailingTimestampSTT:
    async def transcribe_with_word_timestamps(self, audio_bytes: bytes) -> list[WordTiming]:
        raise RuntimeError("simulated Whisper failure")


async def test_speak_with_word_highlight_highlights_each_word_in_order():
    tts = _FakeTTS()
    audio = _FakeAudio()
    face = _FakeFace()
    stt = _FakeSTTWithTimestamps(
        [WordTiming(word="Dan", start=0.0, end=0.01), WordTiming(word="ran", start=0.01, end=0.02)]
    )
    cache: dict = {}

    await _speak_with_word_highlight(tts, audio, face, stt, "Dan ran.", 1.0, cache, 0)

    # Decision 0098's own fix: the expected text's own words ("Dan",
    # "ran.") are substituted in by position -- same count as
    # Whisper's two timings -- not Whisper's raw transcribed text.
    # Matched by (sentence_index, word_position), not word text.
    assert face.reading_text_highlights == [
        (0, 0, "Dan"), (0, 1, "ran."), (0, None, None),
    ]
    assert audio.played == [b"fake-audio"]


async def test_speak_with_word_highlight_scopes_the_highlight_to_its_own_sentence():
    """Found live: "Sam" repeated across sentence 1 and sentence 3 of
    a story lit up in EVERY sentence containing it, not just the one
    actually being modeled, because the highlight was a bare word
    with no sentence context. sentence_index must be threaded straight
    through to the face, unchanged, so the renderer can scope the
    match to just the sentence actually being spoken."""
    tts = _FakeTTS()
    audio = _FakeAudio()
    face = _FakeFace()
    stt = _FakeSTTWithTimestamps([WordTiming(word="Sam", start=0.0, end=0.01)])
    cache: dict = {}

    await _speak_with_word_highlight(tts, audio, face, stt, "Sam can nap.", 1.0, cache, 2)

    assert face.reading_text_highlights == [(2, 0, "Sam"), (2, None, None)]


async def test_speak_with_word_highlight_distinguishes_a_word_from_its_own_repeat():
    """Found live: both "and"s in "Pat and the pup run and run." lit
    up together the instant the first was spoken, since matching by
    word text alone can't tell a repeated word apart from itself.
    Matching by word POSITION can -- each "and" gets its own,
    distinct position."""
    tts = _FakeTTS()
    audio = _FakeAudio()
    face = _FakeFace()
    stt = _FakeSTTWithTimestamps(
        [
            WordTiming(word="Pat", start=0.0, end=0.01),
            WordTiming(word="and", start=0.01, end=0.02),
            WordTiming(word="the", start=0.02, end=0.03),
            WordTiming(word="pup", start=0.03, end=0.04),
            WordTiming(word="run", start=0.04, end=0.05),
            WordTiming(word="and", start=0.05, end=0.06),
            WordTiming(word="run.", start=0.06, end=0.07),
        ]
    )
    cache: dict = {}

    await _speak_with_word_highlight(
        tts, audio, face, stt, "Pat and the pup run and run.", 1.0, cache, 3,
    )

    positions = [pos for _idx, pos, _word in face.reading_text_highlights if pos is not None]
    # Two distinct positions for the two "and"s (index 1 and index
    # 5), not the same position twice.
    assert positions == [0, 1, 2, 3, 4, 5, 6]
    assert len(set(positions)) == len(positions)


async def test_speak_with_word_highlight_holds_the_last_word_before_clearing():
    """Found live: the last word's highlight used to be cleared the
    instant it was set -- nothing waited between setting it and the
    finally block clearing it again, so it never had any real time
    to actually render. Every other word's highlight naturally
    persists until the NEXT word's start time overwrites it; the
    last word has no "next" to wait for, so it must be held for its
    own remaining duration instead."""
    tts = _FakeTTS()
    audio = _FakeAudio()
    face = _FakeFace()
    stt = _FakeSTTWithTimestamps(
        [WordTiming(word="Dan", start=0.0, end=0.01), WordTiming(word="ran.", start=0.01, end=0.05)]
    )
    cache: dict = {}
    sleep_delays: list[float] = []

    async def _tracking_sleep(delay):
        sleep_delays.append(delay)

    with patch("asyncio.sleep", _tracking_sleep):
        await _speak_with_word_highlight(tts, audio, face, stt, "Dan ran.", 1.0, cache, 0)

    # A delay close to the last word's own duration (0.05 - 0.01 =
    # 0.04s) must be slept through BEFORE the highlight clears.
    assert any(delay > 0.03 for delay in sleep_delays)


async def test_speak_with_word_highlight_reuses_the_cache_for_a_repeated_sentence():
    """Decision 0098's actual point: the same (text, speed) modeled
    twice in one call (the up-front whole-story read-through, then
    again for a flagged sentence's own reread) must not pay for a
    second TTS call or a second Whisper timestamp lookup."""
    tts = _FakeTTS()
    audio = _FakeAudio()
    face = _FakeFace()
    stt = _FakeSTTWithTimestamps([WordTiming(word="Dan", start=0.0, end=0.01)])
    cache: dict = {}

    await _speak_with_word_highlight(tts, audio, face, stt, "Dan ran.", 1.0, cache, 0)
    await _speak_with_word_highlight(tts, audio, face, stt, "Dan ran.", 1.0, cache, 0)

    assert len(tts.synthesized) == 1
    assert stt.timestamp_calls == 1
    assert len(audio.played) == 2  # still actually spoken both times


# -- _weakest_mastery_for_miscues() / _give_brief_callout() (decision 0103) --


def _substitution(expected: str) -> Miscue:
    return Miscue(kind="substitution", expected=expected, spoken="x", position=0)


def test_weakest_mastery_for_miscues_returns_the_lowest_tracked_grapheme():
    profile = ReadingProfile(child_profile_id="child-1")
    profile.masteries["c"] = GraphemeMastery(grapheme="c", level="short_vowels", p_mastery=0.9)
    profile.masteries["a"] = GraphemeMastery(grapheme="a", level="short_vowels", p_mastery=0.95)
    profile.masteries["t"] = GraphemeMastery(grapheme="t", level="short_vowels", p_mastery=0.95)

    weakest = _weakest_mastery_for_miscues([_substitution("cat")], profile)

    assert weakest == 0.9  # "c" is the weakest of cat's own three graphemes


def test_weakest_mastery_for_miscues_treats_an_untracked_grapheme_as_zero():
    """Decision 0103: never having been observed at all is at least
    as strong a reason to prioritize a sentence as any tracked-but-
    weak grapheme, not a reason to skip it."""
    profile = ReadingProfile(child_profile_id="child-1")
    profile.masteries["i"] = GraphemeMastery(grapheme="i", level="short_vowels", p_mastery=0.95)
    profile.masteries["g"] = GraphemeMastery(grapheme="g", level="short_vowels", p_mastery=0.95)
    # "p" is never tracked at all.

    weakest = _weakest_mastery_for_miscues([_substitution("pig")], profile)

    assert weakest == 0.0


def test_weakest_mastery_for_miscues_skips_insertions_with_no_expected_word():
    profile = ReadingProfile(child_profile_id="child-1")
    insertion = Miscue(kind="insertion", expected=None, spoken="really", position=1)

    # Nothing to decompose, nothing tracked -- no crash, stays at the
    # default "fully mastered" baseline since nothing pulled it down.
    assert _weakest_mastery_for_miscues([insertion], profile) == 1.0


async def test_give_brief_callout_names_each_word_without_a_hint_ladder():
    """Decision 0115, found live: this used set_reading_spotlight(),
    which (despite the function's own docstring already claiming
    "the whole story stays visible") replaces the whole view -- the
    same isolated-view bug decisions 0112/0113 already fixed
    elsewhere, just missed here. Now highlights each word in place
    within the sentence instead."""
    tts = _FakeTTS()
    audio = _FakeAudio()
    face = _FakeFace()

    await _give_brief_callout(["cat", "bat"], 2, "The cat and the bat flew.", tts, audio, face, 1.0)

    assert any('"cat' in line for line in tts.synthesized)
    assert any('"bat' in line for line in tts.synthesized)
    # Highlighted in place within sentence 2 ("cat" is word index 1,
    # "bat" is word index 4), then cleared -- never the full
    # hint-ladder/reread treatment's own lines.
    assert face.reading_text_highlights == [(2, 1, "cat"), (2, 4, "bat"), (2, None, None)]
    assert not any("sound it out" in line for line in tts.synthesized)


async def test_speak_with_word_highlight_falls_back_when_stt_lacks_the_capability():
    tts = _FakeTTS()
    audio = _FakeAudio()
    face = _FakeFace()
    cache: dict = {}

    await _speak_with_word_highlight(tts, audio, face, "fake-stt", "Dan ran.", 1.0, cache, 0)

    assert face.reading_text_highlights == []
    assert audio.played == [b"fake-audio"]


async def test_speak_with_word_highlight_falls_back_when_the_timestamp_lookup_fails():
    tts = _FakeTTS()
    audio = _FakeAudio()
    face = _FakeFace()
    cache: dict = {}

    await _speak_with_word_highlight(
        tts, audio, face, _FailingTimestampSTT(), "Dan ran.", 1.0, cache, 0,
    )

    assert face.reading_text_highlights == []
    assert audio.played == [b"fake-audio"]


# -- reread + word-meaning check after a hint-ladder word (decision 0074) --


async def test_run_reading_partner_rereads_and_checks_meaning_after_a_hint():
    """Decision 0074, from a product-owner critique: a hint-ladder word
    doesn't just get hinted and dropped -- the sentence is reread once
    for fluency, then one comprehension question anchored to that word
    checks whether the child understood its meaning/role in the
    sentence, with decision 0062's scaffolded retry if the first
    answer is wrong."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="The frog jumps over the log.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            # "frog" resolves on the very first hint stage, which also
            # triggers decision 0066's word-family check before this
            # turn's own word-meaning question -- no "WORD:" lines
            # here means no candidates, so it's a silent no-op.
            ("unused -- word family finds no candidates", "fake-model"),
            ("QUESTION: What jumps over the log?", "fake-model"),  # word-meaning question
            ("STATUS: needs_retry\nSAY: Good try! Think about what hops.", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, the frog!", "fake-model"),  # resolves on the retry
            ("Sorry, no questions.", "fake-model"),  # book-level comprehension -- skipped
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # decision 0085: declines Chitti's "read it to you first?" offer
        "the dog jumps over the log",  # read-aloud -- "frog" substituted as "dog"
        "frog",  # resolved on the very first hint stage
        "the frog jumps over the log",  # decision 0074/0084: the sentence reread
        "a dog",  # wrong first answer to the word-meaning question
        "the frog",  # correct on the retry
        "no thanks",  # declines the word game
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "I'll read it for you first. Listen:" in tts.synthesized
    assert "Now it's your turn! Give it a try." in tts.synthesized
    assert "Nice reading!" in tts.synthesized
    assert "What jumps over the log?" in tts.synthesized
    assert "Good try! Think about what hops." in tts.synthesized
    assert "Yes, the frog!" in tts.synthesized


async def test_run_reading_partner_catches_a_new_miscue_introduced_during_the_reread():
    """Decision 0081, from a product-owner critique of a real
    transcript: a child's missed word still didn't resolve on the
    retry, then on the reread they swapped "big" for "bug" -- a brand
    new miscue in a word that was never missed before. Chitti must
    not say "Nice reading!" regardless; it should notice "big" is now
    wrong and run one short correction cycle for that specific word."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="He can hop on the big bus.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("QUESTION: What can he do on the bus?", "fake-model"),  # word-meaning question
            ("STATUS: resolved\nSAY: Yes, he can hop!", "fake-model"),  # resolves immediately
            ("Sorry, no questions.", "fake-model"),  # book-level comprehension -- skipped
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # decision 0085: declines Chitti's "read it to you first?" offer
        "he cat hop on the big bus",  # read-aloud -- "can" substituted as "cat"
        "nope",  # decision 0116: the one retry for "can" -- still wrong
        "he can hop on the bug bus",  # reread -- "big" now swapped for "bug"
        "big",  # decision 0081's correction attempt -- resolves
        "to hop",  # answers the word-meaning question, first try
        "no thanks",  # declines the word game
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "I'll read it for you first. Listen:" in tts.synthesized
    assert "Now it's your turn! Give it a try." in tts.synthesized
    assert "Let's look at this word again. Listen: big." in tts.synthesized
    assert 'Yes, "big"! Nice fixing that.' in tts.synthesized
    # The reread introduced a real miscue -- never blanket-praised.
    assert "Nice reading!" not in tts.synthesized


async def test_run_reading_partner_skips_the_word_meaning_check_on_a_clean_read():
    """No hint-ladder word this turn -- no reread, no word-meaning
    question at all."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures("no thanks", "a cat sat", "no thanks", "let's just chat"):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # Decision 0084/0085: the reread/model-then-repeat text never
    # appears -- a clean read has no hint_words, so that whole block
    # never runs.
    assert "I'll read it for you first. Listen:" not in tts.synthesized
    assert "Now it's your turn! Give it a try." not in tts.synthesized
    assert len(llm.calls) == 1  # only the book-level comprehension-questions call


# -- sentence-by-sentence reading with persistent position (decision 0067) --


async def test_run_reading_partner_shows_and_captures_the_whole_story_in_one_take():
    """Decision 0095: the child reads the entire passage in one
    continuous take -- no per-sentence capture, no mid-passage resume
    (there's no meaningful midpoint any more)."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat. A dog ran.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        # Decision 0094: the offer is asked once per call. Decision
        # 0095: one capture for the whole two-sentence story, read
        # cleanly -- both sentences are skipped by the correction
        # pass below, with no further capture needed.
        "no thanks", "a cat sat a dog ran", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # Decision 0093: the whole two-sentence passage is shown once, set
    # before the single whole-story capture, and only cleared once
    # the whole passage is done -- never swapped sentence by sentence
    # (there's room for the whole story on a TV over HDMI).
    assert [lines for lines in face.reading_texts if lines] == [["A cat sat.", "A dog ran."]]


async def test_run_reading_partner_keeps_the_story_on_screen_through_comprehension_and_word_game():
    """Decision 0112: found live -- the story used to be cleared right
    after the read-aloud/correction finished, before comprehension
    questions and the word game ran, so the child answered both
    completely blind. It must stay visible (not cleared) all the way
    through both -- only the mode's own final clear-on-exit may clear
    it, and that happens exactly once, at the very end."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A little bunny hops.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # decline the "read it to you first?" offer
        "a little bunny hops",  # perfect read-aloud
        "no thanks",  # decline the word game -- nothing more to capture
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # set_reading_text(None) is called exactly once in this whole
    # session -- the mode's own final clear-on-exit -- not once right
    # after the read-aloud finished and again at the very end.
    assert face.reading_texts.count(None) == 1
    assert face.reading_texts[-1] is None


async def test_run_reading_partner_reaches_the_second_sentence_after_the_first_needed_the_full_hint_flow():
    """A product-owner report of a real transcript ("Dan and the Dog")
    worried that a multi-sentence passage stays stuck on sentence 1
    forever once it triggers the hint ladder + reread +
    word-meaning-check detour. Decision 0095: confirms the
    correction loop over every sentence's own bucketed miscues still
    reaches sentence 2 after all of that runs for sentence 1 -- and
    that sentence 2, read cleanly in the one whole-story capture, is
    simply skipped rather than re-asked."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="Dan had a dog. The dog ran.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("unused -- word family finds no candidates", "fake-model"),  # decision 0066
            ("QUESTION: What did Dan have?", "fake-model"),  # word-meaning question
            ("STATUS: resolved\nSAY: Yes, a dog!", "fake-model"),  # resolves immediately
            ("Sorry, no questions.", "fake-model"),  # book-level comprehension -- skipped
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        # Decision 0094: the "read it to you first?" offer is asked
        # once per call now, not once per sentence. Decision 0095:
        # one whole-story capture, not one per sentence -- "had" is
        # substituted as "has" in sentence 1 only, so sentence 2 has
        # no miscues and is skipped entirely by the correction pass.
        "no thanks",  # declines the offer for the whole call
        "dan has a dog the dog ran",  # whole-story read-aloud, one miss
        "had",  # resolves on the first hint stage
        "dan had a dog",  # sentence 1's reread -- clean
        "a dog",  # answers the word-meaning question, first try
        "no thanks",  # declines the word game
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # Sentence 1's hint detour (including its own reread) didn't trap
    # the loop there -- sentence 2, read cleanly, is simply skipped.
    # Decision 0093/0113: the whole passage is shown once and stays up
    # the entire time -- no narrowing to just the flagged sentence for
    # its own correction any more -- sentence 2 needs no display
    # change of its own, since it's never revisited.
    assert [lines for lines in face.reading_texts if lines] == [
        ["Dan had a dog.", "The dog ran."],
    ]
    # "had" is sentence 1's own word index 1 ("Dan had a dog.") --
    # highlighted in place, in the (still fully visible) story.
    assert (0, 1, "had") in face.reading_text_highlights
    assert "Nice reading!" in tts.synthesized
    assert "Yes, a dog!" in tts.synthesized


async def test_run_reading_partner_highlight_uses_the_real_story_index():
    """Decision 0113: the story is no longer narrowed to just the
    flagged sentence during its own correction (decision 0112's own
    "keep the story visible" fix, extended here) -- the highlight
    must use the sentence's own REAL index in the whole story (here,
    sentence 2 of 2 is story index 1), or it would light up the wrong
    page (or nothing) now that every page is actually on screen.
    (Decision 0098 originally hardcoded this to 0 for the opposite
    reason -- back when the display WAS narrowed to one page.)"""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="Dan had a dog. The dog ran.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("unused -- word family finds no candidates", "fake-model"),
            ("QUESTION: What did the dog do?", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, it ran!", "fake-model"),
            ("Sorry, no questions.", "fake-model"),
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()
    stt = _FakeSTTWithTimestamps([WordTiming(word="x", start=0.0, end=0.01)])

    with _patch_captures(
        "no thanks",  # declines the up-front read -- isolates this
        # test to the per-sentence correction block's own highlight
        # calls, the ones decision 0098's fix actually touches.
        "dan had a dog the dog hopped",  # sentence 2's own miss
        "ran",  # resolves on the first hint stage
        "the dog ran",  # sentence 2's reread -- clean
        "it ran",  # answers the word-meaning question
        "no thanks",
        "let's just chat",
    ):
        await _run_reading_partner(
            conversation, tts, _FakeAudio(), stt,
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert face.reading_text_highlights
    assert all(index == 1 for index, _position, _word in face.reading_text_highlights)
    # Decision 0102: this sentence gets a highlighted read twice in
    # this one correction block -- once under "Let's work on this
    # one", again under "I'll read it for you first" -- now at the
    # same speed, so the second one reuses the first's cached audio
    # and timestamps instead of a second Whisper lookup.
    assert stt.timestamp_calls == 1


async def test_run_reading_partner_tiers_correction_by_weakest_tracked_mastery():
    """Decision 0103: a story with more flagged sentences than
    _MAX_FULL_CORRECTIONS (2) tiers the response -- the two whose
    misses touch the weakest tracked grapheme mastery get the full
    hint-ladder/reread/word-meaning-check treatment; the rest get
    one brief callout instead of being skipped. Here "cat" (its own
    weakest grapheme, "c", tracked at 0.9) loses out to "bat" ("b"
    at 0.5) and "pig" ("p", never tracked at all -- treated as 0.0,
    the weakest of all three)."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="Dan has a cat. Sam has a bat. The pig ran fast.",
            created_at=datetime.now(timezone.utc),
        )
    )
    # Shared graphemes ("a", "t") tracked high so they never dominate
    # over each word's own distinguishing letter; "p" ("pig") is left
    # untracked entirely.
    profile = reading.get_or_create("child-1")
    for grapheme, p_mastery in [("a", 0.95), ("t", 0.95), ("i", 0.95), ("g", 0.95), ("c", 0.9), ("b", 0.5)]:
        profile.masteries[grapheme] = GraphemeMastery(
            grapheme=grapheme, level="short_vowels", p_mastery=p_mastery,
        )
    reading.save(profile)

    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("unused -- word family finds no candidates", "fake-model"),  # "bat"
            ("QUESTION: What did Sam have?", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, a bat!", "fake-model"),
            ("unused -- word family finds no candidates", "fake-model"),  # "pig"
            ("QUESTION: What did the pig do?", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, it ran!", "fake-model"),
            ("Sorry, no questions.", "fake-model"),  # book-level comprehension -- skipped
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # declines the up-front read
        "dan has a hat sam has a mat the wig ran fast",  # 3 misses, one per sentence
        "bat",  # resolves "bat" on the first hint stage
        "sam has a bat",  # sentence 1's reread -- clean
        "a bat",  # answers the word-meaning question
        "pig",  # resolves "pig" on the first hint stage
        "the pig ran fast",  # sentence 2's reread -- clean
        "it ran",  # answers the word-meaning question
        "no thanks",  # declines the word game
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # "cat" got the brief callout, not the full treatment -- its own
    # sentence is never spoken as a highlighted modeled read, and
    # "Let's work on this one" (the full-correction intro) never
    # fires for it.
    assert any('"cat' in line for line in tts.synthesized)
    assert "Dan has a cat." not in tts.synthesized
    # "bat" and "pig" both got the full treatment -- their own
    # sentences were spoken as a highlighted modeled read, and the
    # intro line fired for each.
    assert "Sam has a bat." in tts.synthesized
    assert "The pig ran fast." in tts.synthesized
    assert tts.synthesized.count("Let's work on this one:") == 2
    assert "Yes, a bat!" in tts.synthesized
    assert "Yes, it ran!" in tts.synthesized


# Decision 0095: the old per-sentence mid-passage resume (decision
# 0067's `current_passage_key`/`current_sentence_index`) was removed
# along with per-sentence capture -- one whole-story take has no
# meaningful midpoint to resume from any more, so the test that
# covered it (`test_run_reading_partner_resumes_mid_passage_after_an_interrupted_session`)
# no longer applies and was deleted rather than patched.


# -- library-story selection by phase (decision 0104) ----------------------


async def test_run_reading_partner_uses_a_library_book_when_a_phase_is_preferred():
    """Decision 0104: a parent-chosen phase is tried before any LLM
    generation -- the fake LLM's book-generation reply is never
    consumed at all (only its 3 comprehension-reaction replies are),
    confirming generate_decodable_book() was skipped entirely, not
    just that the library book happened to look similar."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    llm = _FakeLLM(reply="unused -- book generation must never be called")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("STATUS: resolved\nSAY: Yes, at the mat!", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, a rat!", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, mad!", "fake-model"),
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # declines the up-front "read it to you first?" offer
        "sam sat sam sat at the mat a rat sat at the mat sam is mad at the rat",  # perfect read
        "at the mat",  # Q1
        "a rat",  # Q2
        "mad",  # Q3
        "no thanks",  # declines the word game
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
            preferred_phase=1,
        )

    assert next_mode == "3"
    # Phase 1's own order=1 story ("Sam Sat"), not an LLM-generated one.
    assert any("Sam Sat" in line for line in tts.synthesized)
    # Its own pre-written questions, spoken verbatim.
    assert "Where did Sam sit?" in tts.synthesized
    assert "Who else sat at the mat?" in tts.synthesized
    assert "How did Sam feel about the rat?" in tts.synthesized
    # Exactly the 3 reaction replies were consumed -- confirms
    # generate_comprehension_questions() (which would have been a 4th,
    # earlier call) was never made either.
    assert llm.generate_reply.call_count == 3

    profile = reading.get_or_create("child-1")
    assert profile.completed_library_stories == ["sam-sat"]


async def test_run_reading_partner_serves_the_next_library_story_not_a_repeat():
    """A second call with the same preferred phase gets the next
    story in the phase, not the one already marked complete."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    profile = reading.get_or_create("child-1")
    profile.completed_library_stories = ["sam-sat"]
    reading.save(profile)

    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("STATUS: resolved\nSAY: Yes, the cat!", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, mad!", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, the rat rid the mat!", "fake-model"),
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",
        "the cat is at the mat the rat is at the mat the cat is mad the rat is sad the cat sat the rat sat",
        "the cat",
        "mad",
        "the rat rid the mat",
        "no thanks",
        "let's just chat",
    ):
        await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
            preferred_phase=1,
        )

    assert any("The Cat at the Mat" in line for line in tts.synthesized)
    assert reading.get_or_create("child-1").completed_library_stories == ["sam-sat", "the-cat-at-the-mat"]


# -- re-reading a finished exercise + themed follow-up (decision 0068) ----


async def test_run_reading_partner_offers_to_reread_a_finished_exercise_next_session():
    """Decision 0068: once a parent-uploaded exercise has been read
    and there's no new one waiting, a LATER session offers to read it
    again -- accepting re-serves the exact same passage, voice-driven,
    no parent-dashboard change needed."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()

    # Session 1: read the exercise once, consuming it.
    with _patch_captures("no thanks", "a cat sat", "no thanks", "let's just chat"):
        await _run_reading_partner(
            conversation, _FakeTTS(), _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )
    assert reading_exercises.list_for_child("child-1")[0].consumed_at is not None

    # Session 2 (separate call): no new exercise waiting -- offered a
    # re-read of the one already finished, and accepts it. "yes"
    # answers the whole-story reread offer; "no thanks" then declines
    # decision 0085's per-sentence "read it to you first?" offer.
    tts2 = _FakeTTS()
    with _patch_captures("yes", "no thanks", "a cat sat", "no thanks", "let's just chat"):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts2, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert any('"Homework"' in line for line in tts2.synthesized)
    assert tts2.synthesized[0] == 'Would you like to read "Homework" again, or try something new?'
    # The same passage was shown again, verbatim.
    assert ["A cat sat."] in [lines for lines in face.reading_texts if lines]


def test_classify_reread_reply_recognizes_the_story_title_as_a_yes():
    """Decision 0080, found live (twice): a child answers by naming
    the story itself, not with an actual yes/no word -- the most
    natural way to say "that one" to this specific question."""
    assert _classify_reread_reply("The little frog", "The little frog") is True
    assert _classify_reread_reply("the little frog story", "The little frog") is True


def test_classify_reread_reply_recognizes_new_as_a_no():
    """Decision 0080: "new"/"something new" is the natural way to
    decline THIS specific two-choice question, but isn't a generic
    negative word classify_affirmative() alone would catch."""
    assert _classify_reread_reply("new", "The little frog") is False
    assert _classify_reread_reply("something new please", "The little frog") is False
    assert _classify_reread_reply("let's do something else", "The little frog") is False


def test_classify_reread_reply_still_recognizes_plain_yes_and_no():
    assert _classify_reread_reply("yes", "The little frog") is True
    assert _classify_reread_reply("no thanks", "The little frog") is False


def test_classify_reread_reply_returns_none_for_genuinely_unclear_text():
    assert _classify_reread_reply("let's just chat", "The little frog") is None
    assert _classify_reread_reply("", "The little frog") is None


# -- _classify_read_first_offer_reply (decision 0087) ----------------------


def test_classify_read_first_offer_reply_recognizes_you_as_a_yes():
    """Found live: a real reply to "Would you like me to read it to
    you first?" was just "you" -- not in classify_affirmative()'s
    generic vocabulary at all, so it was wrongly read as a decline."""
    assert _classify_read_first_offer_reply("you") is True
    assert _classify_read_first_offer_reply("you read it") is True
    assert _classify_read_first_offer_reply("you do it first") is True


def test_classify_read_first_offer_reply_still_recognizes_plain_yes_and_no():
    assert _classify_read_first_offer_reply("yes") is True
    assert _classify_read_first_offer_reply("yes please") is True
    assert _classify_read_first_offer_reply("no") is False
    assert _classify_read_first_offer_reply("no thanks") is False


def test_classify_read_first_offer_reply_defaults_to_false_when_unclear():
    """Unclear defaults to the child reading it themselves -- the
    original, always-safe behavior, not a guess either way."""
    assert _classify_read_first_offer_reply("let's just chat") is False
    assert _classify_read_first_offer_reply("") is False


async def test_run_reading_partner_naming_the_story_accepts_the_reread_offer_immediately():
    """Decision 0080, end to end: naming the story itself -- the
    natural way a child answers this question -- re-reads it right
    away, on the very first try, not just "doesn't get lost" like
    decision 0079 alone guaranteed."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()

    with _patch_captures("no thanks", "a cat sat", "no thanks", "let's just chat"):
        await _run_reading_partner(
            conversation, _FakeTTS(), _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    tts2 = _FakeTTS()
    with _patch_captures(
        "Homework", "no thanks", "a cat sat", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts2, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    reread_offers = [
        line for line in tts2.synthesized
        if line == 'Would you like to read "Homework" again, or try something new?'
    ]
    assert len(reread_offers) == 1  # accepted on the first ask, never repeated
    assert ["A cat sat."] in [lines for lines in face.reading_texts if lines]


async def test_run_reading_partner_an_unclear_reply_to_the_reread_offer_asks_again_later():
    """Decision 0079, found live: a reply with no yes/no signal at all
    (e.g. the child started reading the story's own title back
    instead of actually answering) used to silently count as a
    decline and permanently lose the chance to go back to a finished
    exercise for the rest of the session. It must not use up the
    one-time offer -- the next book cycle asks again instead of
    falling through to generation for good."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="TITLE: The Dog\nPAGE: A dog ran.")
    conversation = ConversationService(llm)
    face = _FakeFace()

    with _patch_captures("no thanks", "a cat sat", "no thanks", "let's just chat"):
        await _run_reading_partner(
            conversation, _FakeTTS(), _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    tts2 = _FakeTTS()
    with _patch_captures(
        "the little forg",  # unclear -- not a recognized yes or no
        # Decision 0094: the "read it to you first?" offer is asked
        # once for this whole call -- right here, for the freshly
        # generated book -- and the answer (declined) then also
        # applies, with no further asking, to the re-read book later
        # in this same call.
        "no thanks",
        "a dog ran",  # falls through to a freshly generated book this turn
        "no thanks",  # declines its word game
        "yes please",  # wants another one -- stays in Reading Partner
        "yes",  # the SAME reread offer, asked again -- this time accepted
        "a cat sat",  # reads the original exercise again -- no offer re-asked
        "no thanks",
        "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts2, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    reread_offers = [
        line for line in tts2.synthesized
        if line == 'Would you like to read "Homework" again, or try something new?'
    ]
    assert len(reread_offers) == 2  # asked again, not given up on for the rest of the call


async def test_run_reading_partner_declining_reread_falls_back_to_normal_generation():
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()

    with _patch_captures("no thanks", "a cat sat", "no thanks", "let's just chat"):
        await _run_reading_partner(
            conversation, _FakeTTS(), _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    # A function, not a fixed list: generate_decodable_book() may retry
    # the proposer a few times chasing an on-target draft before
    # falling back to the first decodable one -- this just always
    # returns a valid, decodable draft regardless of attempt count,
    # same "never need to predict exactly how many hint-stage captures
    # happen" reasoning the switch-detection test above already uses.
    async def _llm_side_effect(_messages, system_prompt):
        if "decodable" in system_prompt.lower() and "story" in system_prompt.lower():
            return "TITLE: The Dog\nPAGE: A dog ran.", "fake-model"
        return "Sorry, no questions.", "fake-model"

    llm.generate_reply = AsyncMock(side_effect=_llm_side_effect)
    tts2 = _FakeTTS()
    with _patch_captures(
        "no", "no thanks", "a dog ran", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts2, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert ["A dog ran."] in [lines for lines in face.reading_texts if lines]


async def test_run_reading_partner_themes_the_followup_book_on_the_finished_exercise():
    """Decision 0068: right after a parent-uploaded exercise is
    finished, the NEXT generated book (if the child wants another one)
    is themed as a follow-up to that exercise's own text -- verified
    here by checking the exercise's own content reached the actual
    book-generation prompt, not just the generic stored interest."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")

    # A function, not a fixed list: generate_decodable_book() may retry
    # the proposer a few times chasing an on-target draft before
    # falling back to the first decodable one -- this just always
    # returns a valid, decodable draft regardless of attempt count.
    async def _llm_side_effect(_messages, system_prompt):
        if "decodable" in system_prompt.lower() and "story" in system_prompt.lower():
            return "TITLE: The Cat Family\nPAGE: A cat ran.", "fake-model"
        return "Sorry, no questions.", "fake-model"

    llm.generate_reply = AsyncMock(side_effect=_llm_side_effect)
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        # Decision 0094: the "read it to you first?" offer is asked
        # once for this whole call -- declined here, then reused (no
        # further asking) for the follow-up book later in this call.
        "no thanks",
        "a cat sat",  # read-aloud of the exercise
        "no thanks",  # declines the word game
        "yes please",  # wants another one -- stays in Reading Partner
        "a cat ran",  # read-aloud of the themed follow-up book
        "no thanks",  # declines the word game again
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    book_gen_prompt = llm.generate_reply.call_args_list[1].args[1]
    assert "A cat sat." in book_gen_prompt
    assert '"The Cat Family"' in "".join(tts.synthesized)


async def test_run_reading_partner_falls_back_to_a_plain_book_when_the_themed_one_fails():
    """Decision 0071, found live: a themed follow-up failing (the
    passage's own vocabulary fighting the decodability budget) used to
    go straight to the apology, even though a normal, untethered book
    would very likely have succeeded. Now it retries once without
    theming before actually giving up."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")

    async def _llm_side_effect(_messages, system_prompt):
        # The themed attempt's prompt contains the source passage --
        # always return something undecodable (needs digraphs) so it
        # exhausts every retry and raises. The plain fallback's prompt
        # has no source passage at all -- always decodable.
        if "A cat sat." in system_prompt and "decodable" in system_prompt.lower():
            return "TITLE: Bad\nPAGE: A ship sat.", "fake-model"
        if "decodable" in system_prompt.lower() and "story" in system_prompt.lower():
            return "TITLE: The Dog\nPAGE: A dog ran.", "fake-model"
        return "Sorry, no questions.", "fake-model"

    llm.generate_reply = AsyncMock(side_effect=_llm_side_effect)
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        # Decision 0094: the "read it to you first?" offer is asked
        # once for this whole call -- declined here, then reused (no
        # further asking) for the fallback book later in this call.
        "no thanks",
        "a cat sat",  # read-aloud of the exercise
        "no thanks",  # declines the word game
        "yes please",  # wants another one
        "a dog ran",  # read-aloud of the FALLBACK book, not a themed one
        "no thanks",  # declines the word game again
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert not any("having trouble coming up with a story" in line for line in tts.synthesized)
    assert '"The Dog"' in "".join(tts.synthesized)


async def test_run_reading_partner_falls_back_to_the_story_bank_when_everything_fails():
    """Decisions 0077/0078: when BOTH the themed attempt and the plain
    fallback fail, the session no longer ends in an apology at all --
    it falls back to a hand-written, pre-verified natural story from
    the story bank (decision 0078) before ever reaching decision
    0077's word-drill, since the bank has a story for every real
    objective."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")

    async def _always_fails(_messages, system_prompt):
        # Every book-generation attempt (themed or plain) returns
        # something undecodable -- neither ever succeeds.
        if "decodable" in system_prompt.lower() and "story" in system_prompt.lower():
            return "TITLE: Bad\nPAGE: A ship sat.", "fake-model"
        return "Sorry, no questions.", "fake-model"

    llm.generate_reply = AsyncMock(side_effect=_always_fails)
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    # A function, not a fixed list: the fallback builder's own content
    # is deterministic word-practice text, not natural prose, so a
    # fixed "read it back" guess could easily turn into a real miscue
    # and trigger the hint ladder -- an unpredictable number of extra
    # captures. "let's just chat" answers everything after the first
    # four fixed turns; declines/misses it along the way are all
    # harmless, and it's what finally ends the session once the
    # "want another one?" turn sees it too. Decision 0085: the leading
    # "no thanks" declines the exercise's own "read it to you first?"
    # offer, so "a cat sat" still lands on the actual read-aloud.
    scripted = iter(["no thanks", "a cat sat", "no thanks", "yes please"])

    async def _capture_side_effect(*_args, **_kwargs):
        try:
            return next(scripted)
        except StopIteration:
            return "let's just chat"

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=_capture_side_effect,
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert not any("having trouble coming up with a story" in line for line in tts.synthesized)
    from companion_robot.reading.story_bank import _STORY_BANK

    story_titles = {s.title for s in _STORY_BANK}
    assert any(
        any(title in line for title in story_titles) for line in tts.synthesized
    ), "expected a story-bank title, not the word-drill or an apology"


async def test_run_reading_partner_falls_back_to_the_word_drill_when_the_story_bank_also_has_nothing():
    """Decision 0078's own final backstop: if the story bank somehow
    has no match either (forced here -- in practice every real
    objective has at least one), decision 0077's guaranteed word-
    drill still catches it."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")

    async def _always_fails(_messages, system_prompt):
        if "decodable" in system_prompt.lower() and "story" in system_prompt.lower():
            return "TITLE: Bad\nPAGE: A ship sat.", "fake-model"
        return "Sorry, no questions.", "fake-model"

    llm.generate_reply = AsyncMock(side_effect=_always_fails)
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    # Decision 0085: the leading "no thanks" declines the exercise's
    # own "read it to you first?" offer, so "a cat sat" still lands on
    # the actual read-aloud.
    scripted = iter(["no thanks", "a cat sat", "no thanks", "yes please"])

    async def _capture_side_effect(*_args, **_kwargs):
        try:
            return next(scripted)
        except StopIteration:
            return "let's just chat"

    with (
        patch(
            "companion_robot.voice_loop_demo._capture_and_transcribe",
            new_callable=AsyncMock,
            side_effect=_capture_side_effect,
        ),
        patch("companion_robot.voice_loop_demo.pick_story_bank_book", return_value=None),
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert not any("having trouble coming up with a story" in line for line in tts.synthesized)
    assert any("Word" in line for line in tts.synthesized)  # the word-drill's own title shape


# -- post-reading comprehension questions (decision 0059) -----------------


async def test_run_reading_partner_asks_and_reacts_to_comprehension_questions():
    """For an LLM-generated book: questions are generated after the
    feedback line, asked one at a time, and each answer gets a
    story-grounded reaction -- all before the word game."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("TITLE: The Cat\nPAGE: A cat sat.\nPAGE: A cat ran.", "fake-model"),
            ("QUESTION: What did the cat do?\nQUESTION: Where did it sit?", "fake-model"),
            ("STATUS: resolved\nSAY: Great answer! The cat sat down.", "fake-model"),
            ("STATUS: resolved\nSAY: Nice! It sat under a tree.", "fake-model"),
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        # Decision 0094: the "read it to you first?" offer is asked
        # once per call, not once per sentence. Decision 0095: one
        # whole-story capture, read perfectly -- no hint detour for
        # either sentence.
        "no thanks",
        "a cat sat a cat ran",  # the whole story, read perfectly
        "the cat sat down",  # answer to question 1
        "under a tree",  # answer to question 2
        "no thanks",  # declines the word game
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert any("talk about the story" in line.lower() for line in tts.synthesized)
    assert "What did the cat do?" in tts.synthesized
    assert "Where did it sit?" in tts.synthesized
    assert "Great answer! The cat sat down." in tts.synthesized
    assert "Nice! It sat under a tree." in tts.synthesized


async def test_run_reading_partner_comprehension_retry_gives_one_clue_before_resolving():
    """Decision 0062: a wrong/incomplete first answer gets one clue
    and one retry instead of the correct detail being revealed
    immediately -- exactly one extra capture+reaction, then it moves
    on regardless of the second answer."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("QUESTION: What did the cat do?", "fake-model"),
            ("STATUS: needs_retry\nSAY: Good try! What color was the cat?", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, a black cat!", "fake-model"),
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # decision 0085: the sentence's own offer, declined
        "a cat sat",  # the read-aloud
        "it ran",  # wrong/incomplete first answer
        "a black cat",  # the retry
        "no thanks",  # declines the word game
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "Good try! What color was the cat?" in tts.synthesized
    assert "Yes, a black cat!" in tts.synthesized
    # Never revealed the answer on the first, wrong attempt.
    assert tts.synthesized.index("Good try! What color was the cat?") < tts.synthesized.index(
        "Yes, a black cat!"
    )


async def test_run_reading_partner_comprehension_resolved_first_try_never_retries():
    """A resolved first answer must not trigger a second capture at
    all -- confirmed by a side_effect list with no spare entry for one."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("QUESTION: What did the cat do?", "fake-model"),
            ("STATUS: resolved\nSAY: Great job!", "fake-model"),
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures("no thanks", "a cat sat", "it sat", "no thanks", "let's just chat"):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "Great job!" in tts.synthesized


async def test_run_reading_partner_comprehension_questions_also_run_for_an_exercise():
    """Decision 0059's deliberate precedent change: a parent-uploaded
    exercise (decision 0052, otherwise entirely LLM-free) still gets
    comprehension questions about its own text."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("QUESTION: What did the cat do?", "fake-model"),
            ("STATUS: resolved\nSAY: Great answer! The cat sat down.", "fake-model"),
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks", "a cat sat", "the cat sat down", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "What did the cat do?" in tts.synthesized
    assert "Great answer! The cat sat down." in tts.synthesized


async def test_run_reading_partner_skips_comprehension_phase_when_no_questions_parsed():
    """A reply with no "QUESTION:" lines parses to an empty list --
    the whole phase must skip cleanly, speaking nothing and consuming
    no extra capture."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A cat sat.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="Sorry, I don't have any questions.")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures("no thanks", "a cat sat", "no thanks", "let's just chat"):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert not any("talk about the story" in line.lower() for line in tts.synthesized)


# -- post-reading word game (decision 0057) --------------------------------


async def test_run_word_game_declined_plays_no_rounds():
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A little bunny hops.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks", "a little bunny hops", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # The game was offered (a question was asked)...
    assert any("word game" in line.lower() for line in tts.synthesized)
    # ...but declining it means no word was ever blanked/highlighted or
    # revealed.
    assert face.reading_text_highlight_sets == []
    assert not any('"bunny"' in line for line in tts.synthesized)  # never revealed/graded
    assert not any(line in _CLOSING_LINES for line in tts.synthesized)


async def test_run_word_game_accepted_plays_through_both_words():
    """Decision 0112: both missing words are shown, blanked, IN the
    full story at once (not a separate isolated view, one word at a
    time), asked about in ONE combined turn, and reacted to with one
    LLM-generated reply -- not the old two-separate-rounds, no-LLM
    shape."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A little bunny hops.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(
        reply="You got little! And the missing word was bunny -- nice try!"
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # decision 0085: the sentence's own offer, declined
        "a little bunny hops",  # the read-aloud (perfect, no hint)
        "yes",  # accepts the game
        "little",  # one combined answer -- only "little" said, "bunny" missed
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # Both picked words (longest-first: "little" then "bunny") were
    # blanked IN the full story and highlighted together, not in a
    # separate spotlight-only view.
    blanked_page = f"A {blank_vowels('little')} {blank_vowels('bunny')} hops."
    assert [blanked_page] in face.reading_texts
    # Highlighted together (one combined set, not one-at-a-time), then
    # cleared once the reaction's spoken -- exactly these two calls,
    # nothing else touches reading_text_highlights in this session.
    assert face.reading_text_highlight_sets == [{(0, 1), (0, 2)}, None]
    # The story is restored (unblanked) right after the game, one step
    # before the session's own final clear-on-exit (mode switch).
    assert face.reading_texts[-2] == ["A little bunny hops."]
    assert face.reading_texts[-1] is None
    # The LLM's own combined reaction was actually spoken, grounded in
    # the real per-word results -- not a fixed canned pool.
    assert "You got little! And the missing word was bunny -- nice try!" in tts.synthesized
    # The game always ends on a warm note, regardless of the mix of
    # right/wrong answers.
    assert any(line in _CLOSING_LINES for line in tts.synthesized)


async def test_run_word_game_matches_the_sentence_split_already_on_screen():
    """Decision 0114, found live: a real story's own page can bundle
    more than one sentence ("Sam is sad. That is it." as ONE page) --
    different from `sentences` (split_into_sentences(book.text)), what
    the rest of this call actually displays throughout. The word game
    used to blank/restore `book.pages` instead, so finishing it
    visibly re-laid-out the story (5 lines collapsing to 4, two
    sentences merging onto one line) even though nothing about the
    story's own content changed. It must blank and restore the exact
    same `sentences` list already on screen."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            # One single LINE (so exercise_pages, split on "\n", is
            # ONE page) holding two sentences -- the exact shape that
            # broke live.
            title="Homework",
            content="Sam is sad. That is it.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="Nice try on both words!")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures(
        "no thanks",  # declines the "read it to you first?" offer
        "sam is sad that is it",  # perfect read-aloud, no hint ladder
        "yes",  # accepts the word game
        "that",  # one combined answer -- only "that" said, "sam" missed
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # The initial display is the SENTENCE split (two lines), not the
    # one-page exercise content.
    assert face.reading_texts[0] == ["Sam is sad.", "That is it."]
    # The word game's own blanked display keeps that same two-line
    # shape -- "that" is sentence 1 word 0, "sam" is sentence 0 word 0.
    blanked = [f"{blank_vowels('Sam')} is sad.", f"{blank_vowels('That')} is it."]
    assert blanked in face.reading_texts
    assert {(0, 0), (1, 0)} in face.reading_text_highlight_sets
    # Restored to the SAME two-line shape afterward -- never collapsed
    # back into a single-page/exercise-content shape.
    assert face.reading_texts[-2] == ["Sam is sad.", "That is it."]
    assert face.reading_texts[-1] is None
    assert "Nice try on both words!" in tts.synthesized


async def test_run_word_game_no_longer_plays_phonics_sounds_for_a_wrong_answer():
    """Decision 0118: the word game's old reinforcement (decision 0091)
    -- playing each covered grapheme's real recorded sound after a
    wrong word -- is gone, the last place in the reading flow still
    teaching phonics after decision 0116 removed it everywhere else."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="A little bunny hops.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="You got little! The other word was bunny -- nice try!")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()
    audio = _FakeAudio()

    with _patch_captures(
        "no thanks", "a little bunny hops", "yes", "little", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, audio, "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # audio.played also captures every _speak() call's TTS playback
    # (_FakeTTS.synthesize()'s fixed b"fake-audio" placeholder) -- real
    # phonics clips are real WAV PCM, never that exact placeholder.
    # "bunny" (the word missed) decomposes to real-clip-covered
    # graphemes (b/u/n/y) that decision 0091 used to play here --
    # none of that happens any more.
    real_clips = [clip for clip in audio.played if clip != b"fake-audio"]
    assert real_clips == []


async def test_run_word_game_never_offered_when_no_word_qualifies():
    """Every word in this exercise is under the 3-letter minimum --
    the game must not even ask, and must not consume an extra capture
    doing so."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="I am in it.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with _patch_captures("no thanks", "i am in it", "let's just chat"):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert not any("word game" in line.lower() for line in tts.synthesized)
    # Only the mode's own unconditional clear-on-exit cleanup -- no
    # real game round ever ran.
    assert face.spotlights == [None]


# -- decision 0109: idle-greeting nudge, wired into real mode loops -----


async def test_run_teachable_friend_speaks_idle_greeting_before_the_real_reply(monkeypatch):
    """Confirms the hook is actually wired into _run_teachable_friend's
    own loop (not just unit-tested in isolation) -- fires once, before
    the real conversational reply, when the shared idle clock already
    shows a 60+ minute gap."""
    monkeypatch.setattr(
        voice_loop_demo, "_last_interaction_at", datetime.now(timezone.utc) - timedelta(minutes=90)
    )
    conn = connect(":memory:")
    memories = MemoryRepository(conn)
    engagement = EngagementRepository(conn)
    transcripts = TranscriptRepository(conn)
    llm = _FakeLLM(reply="Dogs are great, tell me more!")
    conversation = ConversationService(llm, summarizer_llm=_FakeLLM(reply="NOTHING"))
    tts = _FakeTTS()

    with _patch_captures("let's just chat"):
        await _run_teachable_friend(
            conversation, tts, _FakeAudio(), "fake-stt",
            memories, engagement, transcripts, _FakeFace(), "child-1", 1.0,
            child_name="Anna",
        )

    assert tts.synthesized[0] == (
        "Hey Anna! I'm here if you want to read, play, or tell me something!"
    )


async def test_run_reading_partner_speaks_idle_greeting_at_the_top_of_its_loop(monkeypatch):
    """Same wiring check, for the differently-shaped Reading Partner
    loop (the idle check sits at the very top of its own outer `while
    True`, before book/exercise selection, not beside a capture call
    the way the chat-style modes have it)."""
    monkeypatch.setattr(
        voice_loop_demo, "_last_interaction_at", datetime.now(timezone.utc) - timedelta(minutes=90)
    )
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title="Homework",
            content="I am in it.",
            created_at=datetime.now(timezone.utc),
        )
    )
    llm = _FakeLLM(reply="unused")
    conversation = ConversationService(llm)
    tts = _FakeTTS()

    with _patch_captures("no thanks", "i am in it", "let's just chat"):
        await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, _FakeFace(), "child-1", 1.0,
            child_name="Anna",
        )

    assert tts.synthesized[0] == (
        "Hey Anna! I'm here if you want to read, play, or tell me something!"
    )
