"""Unit tests for decision 0042's hybrid intent detection and voice
picker in voice_loop_demo.py -- real ConversationService/repositories,
fake LLM/tts/audio/stt stand-ins, no real API calls, hardware, or
keyboard input() needed.
"""
import asyncio
import contextlib
from datetime import datetime, timezone
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
from companion_robot.reading.hints import build_hint_line
from companion_robot.reading.repository import ReadingRepository
from companion_robot.reading.word_timing import WordTiming
from companion_robot.reading.word_game import (
    _CLOSING_LINES,
    _CORRECT_RESPONSES,
    blank_vowels,
)
from companion_robot.storage.sqlite import connect
from companion_robot.transcripts.repository import TranscriptRepository
from companion_robot.voice.interfaces import LanguageModelBackend
from companion_robot.voice_loop_demo import (
    _THINKING_FILLERS,
    _classify_read_first_offer_reply,
    _classify_reread_reply,
    _confirm_switch,
    _detect_switch_intent,
    _generate_with_thinking_filler,
    _pick_item_by_voice,
    _resolve_spoken_choice,
    _run_everyday_companion,
    _run_reading_partner,
    _run_teachable_friend,
    _run_word_family_practice,
    _speak_with_word_highlight,
    _speak_while_thinking,
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

    def set_reading_text_highlight(self, word: str | None, sentence_index: int | None) -> None:
        self.reading_text_highlights.append((sentence_index, word))


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

    assert tts.synthesized == [_THINKING_FILLERS[0]]


async def test_speak_while_thinking_stops_after_the_last_filler_when_still_not_done():
    """A Future that's never resolved guarantees task.done() stays
    False for the whole loop -- no real sleep/timing needed to prove
    the function speaks each filler once, in order, and then simply
    stops rather than looping back or repeating one."""
    tts = _FakeTTS()
    face = _FakeFace()
    never_done = asyncio.get_running_loop().create_future()

    await _speak_while_thinking(never_done, tts, _FakeAudio(), face, 1.0)

    assert tts.synthesized == _THINKING_FILLERS  # each spoken once, in order, no repeats


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
        # 0050's thinking filler plays before the real reply; with
        # every fake here fully synchronous internally (no real
        # asyncio suspension anywhere), the background AI-call task
        # never gets a scheduling chance to finish early, so all three
        # fillers play in full before the real reply's own _speak call
        # -- see test_speak_while_thinking_stops_once_the_task_is_done
        # for the early-stop behavior with a real task.
        with patch(
            "companion_robot.voice_loop_demo._speak",
            new_callable=AsyncMock,
            side_effect=[None, None, None, KeyboardInterrupt],
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
            # confirmation prompt, decline acknowledgment, all three of
            # decision 0050's thinking fillers (see the comment in
            # test_carried_over_text_gets_a_real_reply_without_another_capture
            # for why all three play with fully-synchronous fakes),
            # then the real reply
            side_effect=[None, None, None, None, None, KeyboardInterrupt],
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
    # per-sentence loop starts -- cleared once the passage is done and
    # again once the mode loop exits (the `finally`).
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


async def test_run_reading_partner_hint_retry_succeeds_and_feeds_mastery():
    """Decision 0052: a missed word gets a graduated hint; a corrected
    retry is merged into the grading evidence rather than thrown away."""
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
        # precedent); the retry gets it right on the very first hint.
        # Decision 0074: a resolved hint word means the sentence gets
        # reread once ("sat" again). "no thanks" declines decision
        # 0057's post-reading word game.
        "no thanks", "a cat mat", "sat", "a cat sat", "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # [0] story intro, [1] the "read it to you first?" offer, [2] the
    # "give it a try" turn cue, [3] decision 0095's "let's work on
    # this one" attention cue for the one flagged sentence -- all
    # spoken before the hint ladder itself starts.
    assert tts.synthesized[4] == build_hint_line("sat", 0)
    assert tts.synthesized[5] == "There you go!"
    # Not asserted by fixed index from here on -- decision 0074's
    # reread/word-meaning-check step runs a real LLM call wrapped in
    # decision 0050's thinking-filler, whose line count depends on
    # timing, not just content.
    assert any(
        line.startswith("Good try! Reading can be tricky sometimes.")
        for line in tts.synthesized
    )
    # The corrected retry counted as a real extra opportunity, not
    # discarded -- one wrong (from the original read) + one right
    # (from the retry) for the substituted word's first sound.
    profile = reading.get_or_create("child-1")
    assert profile.masteries["s"].opportunities == 2
    # Decision 0053: the actual bug fix -- the display froze on the
    # missed word for the whole hint exchange, then cleared once the
    # loop ended, rather than leaving the child with no idea what was
    # being asked. (A second clear comes from the mode's own cleanup
    # when it exits right after, via the switch to Just Chat.)
    assert face.spotlights == ["sat", None, None]


async def test_run_reading_partner_hint_retry_continues_without_penalty_after_four_misses():
    """Decision 0052/0064: even if the child never gets the hinted
    word right across all four graduated stages, the session
    continues to normal feedback -- no penalty, no infinite loop."""
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
    # declined, before the read-aloud itself. Decision 0084: exhausting
    # the ladder still triggers a reread -- now modeled by Chitti
    # first. "no thanks" declines decision 0057's post-reading word
    # game.
    with _patch_captures(
        "no thanks", "a cat mat", "nope", "nope", "nope", "nope", "a cat mat", "still nope",
        "no thanks", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # [0] story intro, [1] the "read it to you first?" offer, [2] the
    # "give it a try" turn cue, [3] decision 0095's "let's work on
    # this one" attention cue for the one flagged sentence -- all
    # spoken before the hint ladder itself starts.
    assert tts.synthesized[4] == build_hint_line("sat", 0)
    assert tts.synthesized[5] == build_hint_line("sat", 1)
    assert tts.synthesized[6] == build_hint_line("sat", 2)
    assert tts.synthesized[7] == build_hint_line("sat", 3)
    assert "There you go!" not in tts.synthesized
    # Decision 0084: exhausting the ladder still gets the model-then-
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
    # Decision 0055: an unresolved hint word is mentioned again in the
    # final feedback as something to revisit, instead of the old
    # unconditional phonics-sound list.
    assert '"sat"' in feedback_line
    # Decision 0053: the display stayed frozen on the missed word for
    # all four stages (never cleared early just because a retry was
    # wrong), then cleared once the loop gave up (and again on the
    # mode's own exit cleanup, right after). Decision 0081: the
    # reread's own correction cycle spotlights "sat" again (then
    # clears it) on top of that original hint-ladder spotlight.
    assert face.spotlights == ["sat", None, "sat", None, None]


async def test_run_reading_partner_hints_every_real_miss_not_just_the_first():
    """Decision 0065: a read with two real misses gets both hinted in
    turn, not just the first -- and the final stage's evidence
    (where the word was said outright) must not count toward mastery
    the way an earlier, self-sounded-out stage does."""
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
        "little",  # "little" resolved on the very first retry
        "nope", "nope", "nope", "nope",  # "garden" never resolved, exhausts all 4 stages
        "little garden hops",  # decision 0074/0084: the sentence reread after hint practice
        "no thanks",  # declines the word game
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # Both missed words got their own hint sequence, "little" first
    # (reading order).
    assert build_hint_line("little", 0) in tts.synthesized
    assert "There you go!" in tts.synthesized  # "little" resolved
    assert build_hint_line("garden", 0) in tts.synthesized
    assert build_hint_line("garden", 3) in tts.synthesized  # "garden" exhausted the ladder
    # "little" is excluded from the final practice-words mention
    # (resolved live); "garden" still surfaces since it never was.
    feedback_line = next(
        line for line in tts.synthesized if line.startswith("Good try!")
    )
    assert '"garden"' in feedback_line
    assert '"little"' not in feedback_line


async def test_run_reading_partner_final_stage_resolution_does_not_feed_mastery():
    """Decision 0065, Gap B: resolving a word only at the final hint
    stage -- where Chitti has already said the word outright -- is an
    echo, not independent decoding. Its evidence must not be fed into
    mastery the way the three earlier stages' attempts (sounded out
    themselves after a sound/blend cue, even if wrong) still are."""
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
        "no thanks",  # decision 0085: declines Chitti's "read it to you first?" offer
        "a cat mat",  # the read-aloud -- "sat" missed (substituted as "mat")
        "nope", "nope", "nope",  # stages 0, 1, 2 -- wrong, but still real attempts
        "sat",  # stage 3 -- only correct after being told the word outright
        "a cat sat",  # decision 0074/0084: the sentence reread after hint practice
        "no thanks",
        "let's just chat",
    ):
        await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    # "There you go!" is still spoken (the attempt did match), but
    # the grapheme "s" (sat's first sound) only gets 4 opportunities --
    # the original miscue plus the three *earlier* stages' attempts --
    # not 5, which would mean the final, told-the-answer attempt was
    # wrongly counted as a fifth independent opportunity.
    assert "There you go!" in tts.synthesized
    profile = reading.get_or_create("child-1")
    assert profile.masteries["s"].opportunities == 4


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

    with _patch_captures("yes", "cat"):  # "bat" never attempted
        await _run_word_family_practice(
            "sat", conversation, tts, _FakeAudio(), "fake-stt", face, 1.0, 6,
            ["short_vowels"],
        )

    assert "Nice! You got cat." in tts.synthesized
    assert any(line.startswith('Good try! The word is "bat"') for line in tts.synthesized)
    # Not one praise line per correct word -- just the single combined
    # acknowledgment above.
    assert not any(line in _CORRECT_RESPONSES for line in tts.synthesized)


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

    assert face.reading_text_highlights == [(0, "Dan"), (0, "ran"), (0, None)]
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

    assert face.reading_text_highlights == [(2, "Sam"), (2, None)]


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
    transcript: a child resolved "can" via the hint ladder, then on
    the reread swapped "big" for "bug" -- a brand new miscue in a word
    that was never hinted. Chitti must not say "Nice reading!"
    regardless; it should notice "big" is now wrong and run one short
    correction cycle for that specific word."""
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
            # "can" resolves only on the last hint stage (said outright
            # and echoed back) -- decision 0066's word-family check is
            # deliberately skipped for a last-stage resolution, so no
            # word-family LLM call is expected here.
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
        "nope", "nope", "nope",  # hint stages 0-2, still wrong
        "can",  # resolves on the last stage (said outright, echoed back)
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
    # Decision 0093/0095: the whole passage is shown first, narrows
    # to just the flagged sentence for its own correction, then
    # widens back to the whole story once that correction is done --
    # sentence 2 needs no display change of its own, since it's
    # never revisited.
    assert [lines for lines in face.reading_texts if lines] == [
        ["Dan had a dog.", "The dog ran."],
        ["Dan had a dog."],
        ["Dan had a dog.", "The dog ran."],
    ]
    assert "Nice reading!" in tts.synthesized
    assert "Yes, a dog!" in tts.synthesized


# Decision 0095: the old per-sentence mid-passage resume (decision
# 0067's `current_passage_key`/`current_sentence_index`) was removed
# along with per-sentence capture -- one whole-story take has no
# meaningful midpoint to resume from any more, so the test that
# covered it (`test_run_reading_partner_resumes_mid_passage_after_an_interrupted_session`)
# no longer applies and was deleted rather than patched.


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
    # ...but declining it means no word was ever shown or revealed --
    # the only spotlight call is the mode's own unconditional
    # clear-on-exit cleanup, not a real round.
    assert face.spotlights == [None]
    assert not any(line in _CORRECT_RESPONSES for line in tts.synthesized)
    assert not any('"bunny"' in line for line in tts.synthesized)  # never revealed/graded
    assert not any(line in _CLOSING_LINES for line in tts.synthesized)


async def test_run_word_game_accepted_plays_through_both_words():
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
        "no thanks",  # decision 0085: the sentence's own offer, declined
        "a little bunny hops",  # the read-aloud (perfect, no hint)
        "yes",  # accepts the game
        "little",  # round 1 ("little"): correct
        "nope",  # round 2 ("bunny"): incorrect
        "let's just chat",  # ends the session
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # Both picked words (longest-first: "little" then "bunny") were
    # shown, blanked, on screen -- and cleared again after each round
    # (plus once more from the mode's own clear-on-exit cleanup).
    assert face.spotlights == [
        blank_vowels("little"), None, blank_vowels("bunny"), None, None,
    ]
    # Round 1's correct answer got one of the fixed celebratory replies.
    assert any(line in _CORRECT_RESPONSES for line in tts.synthesized)
    # Round 2's wrong answer still named the real word, gently.
    assert any('"bunny"' in line for line in tts.synthesized)
    # The game always ends on a warm note, regardless of the mix of
    # right/wrong answers.
    assert any(line in _CLOSING_LINES for line in tts.synthesized)


async def test_run_word_game_plays_real_phonics_sounds_for_a_wrong_answer():
    """Decision 0091: a wrong answer still gets the spoken "'b' like
    in 'bat'..." breakdown unchanged (word_game.py's own
    incorrect_response()), but now also plays each covered grapheme's
    real recorded sound right after it -- reinforcement with the
    actual phoneme, not just the proxy word."""
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
    audio = _FakeAudio()

    with _patch_captures(
        "no thanks", "a little bunny hops", "yes", "little", "nope", "let's just chat",
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, audio, "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # audio.played also captures every _speak() call's TTS playback
    # (_FakeTTS.synthesize()'s fixed b"fake-audio" placeholder) -- real
    # phonics clips are real WAV PCM, never that exact placeholder.
    # "bunny" decomposes to b/u/n/y (one grapheme per sound -- "nn" is
    # one /n/, not two); every one of those has a real clip except "y"
    # (decision 0091's DEFERRED_GRAPHEMES) -- 3 real clips played.
    real_clips = [clip for clip in audio.played if clip != b"fake-audio"]
    assert len(real_clips) == 3


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
