"""Unit tests for decision 0042's hybrid intent detection and voice
picker in voice_loop_demo.py -- real ConversationService/repositories,
fake LLM/tts/audio/stt stand-ins, no real API calls, hardware, or
keyboard input() needed.
"""
import asyncio
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
    _confirm_switch,
    _detect_switch_intent,
    _generate_with_thinking_filler,
    _pick_item_by_voice,
    _resolve_spoken_choice,
    _run_everyday_companion,
    _run_reading_partner,
    _run_teachable_friend,
    _speak_while_thinking,
)


@pytest.fixture(autouse=True)
def _reading_exercises_enabled(monkeypatch):
    """Decision 0063 made decision 0052's parent-uploaded exercises
    opt-in behind CHITTI_ENABLE_READING_EXERCISES=1 (default off).
    Most Reading Partner tests in this file use a pending exercise
    purely as a convenient, deterministic content fixture -- not to
    test the exercise feature itself -- so this keeps that pattern
    working for all of them; test_run_reading_partner_exercise_is_* in
    this file is the one place that explicitly asserts the flag's own
    on/off behavior, overriding this fixture with monkeypatch.delenv().
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
        self.reading_texts: list[list[str] | None] = []
        self.spotlights: list[str | None] = []

    def set_status_led(self, state: DeviceState) -> None:
        self.states.append(state)

    def set_expression_mode(self, mode: str | None) -> None:
        self.modes.append(mode)

    def set_reading_text(
        self, lines: list[str] | None, *, wpm: float = 45.0, font_size: int = 28,
        font_color: str = "white",
    ) -> None:
        self.reading_texts.append(lines)

    def set_reading_spotlight(self, word: str | None) -> None:
        self.spotlights.append(word)


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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        # A perfect read -- no miscue, so decision 0052's hint loop
        # never fires here and doesn't consume extra captures. "no
        # thanks" declines decision 0057's post-reading word game
        # (offered since "cat"/"sat"/"ran" all qualify) so it never
        # consumes further captures either. The final turn is a
        # genuine switch request (needed so the mode loop -- which
        # otherwise keeps generating books forever -- actually
        # terminates for this test).
        side_effect=["a cat sat a cat ran", "no thanks", "let's just chat"],
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
    # The book's text was actually shown on screen, then cleared both
    # before grading and again once the mode loop exits (the `finally`).
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        # "no thanks" declines decision 0057's post-reading word game.
        side_effect=["the cat sat", "no thanks", "let's just chat"],
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


async def test_run_reading_partner_exercise_is_ignored_when_flag_is_off(monkeypatch):
    """Decision 0063: with CHITTI_ENABLE_READING_EXERCISES unset
    (the real default), a pending exercise must be completely ignored
    -- never read, never consumed -- even though one exists. Every
    book comes from the LLM path instead."""
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
    llm = _FakeLLM(reply="TITLE: The Dog\nPAGE: A dog ran.")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=["a dog ran", "no thanks", "let's just chat"],
    ):
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        # "no thanks" declines decision 0057's post-reading word game.
        side_effect=["a little bunny hops", "no thanks", "let's just chat"],
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        # "mat" for "sat" is a clean substitution (test_reading_alignment's
        # own precedent); the retry gets it right on the very first
        # hint. "no thanks" declines decision 0057's post-reading word game.
        side_effect=["a cat mat", "sat", "no thanks", "let's just chat"],
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # [0] is the story intro, spoken before the read-aloud capture.
    assert tts.synthesized[1] == build_hint_line("sat", 0)
    assert tts.synthesized[2] == "There you go!"
    assert tts.synthesized[3].startswith("Good try! Reading can be tricky sometimes.")
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


async def test_run_reading_partner_hint_retry_continues_without_penalty_after_three_misses():
    """Decision 0052: even if the child never gets the hinted word
    right, the session continues to normal feedback after the third
    stage -- no penalty, no infinite loop."""
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        # "no thanks" declines decision 0057's post-reading word game.
        side_effect=["a cat mat", "nope", "nope", "nope", "no thanks", "let's just chat"],
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    # [0] is the story intro, spoken before the read-aloud capture.
    assert tts.synthesized[1] == build_hint_line("sat", 0)
    assert tts.synthesized[2] == build_hint_line("sat", 1)
    assert tts.synthesized[3] == build_hint_line("sat", 2)
    assert "There you go!" not in tts.synthesized
    assert tts.synthesized[4].startswith("Good try! Reading can be tricky sometimes.")
    # Decision 0055: an unresolved hint word is mentioned again in the
    # final feedback as something to revisit, instead of the old
    # unconditional phonics-sound list.
    assert '"sat"' in tts.synthesized[4]
    # Decision 0053: the display stayed frozen on the missed word for
    # all three stages (never cleared early just because a retry was
    # wrong), then cleared once the loop gave up (and again on the
    # mode's own exit cleanup, right after).
    assert face.spotlights == ["sat", None, None]


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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=[
            "a cat sat a cat ran",  # the read-aloud (perfect, no hint)
            "the cat sat down",  # answer to question 1
            "under a tree",  # answer to question 2
            "no thanks",  # declines the word game
            "let's just chat",  # ends the session
        ],
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=[
            "a cat sat",  # the read-aloud
            "it ran",  # wrong/incomplete first answer
            "a black cat",  # the retry
            "no thanks",  # declines the word game
            "let's just chat",  # ends the session
        ],
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=["a cat sat", "it sat", "no thanks", "let's just chat"],
    ):
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=["a cat sat", "the cat sat down", "no thanks", "let's just chat"],
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=["a cat sat", "no thanks", "let's just chat"],
    ):
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=["a little bunny hops", "no thanks", "let's just chat"],
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=[
            "a little bunny hops",  # the read-aloud (perfect, no hint)
            "yes",  # accepts the game
            "little",  # round 1 ("little"): correct
            "nope",  # round 2 ("bunny"): incorrect
            "let's just chat",  # ends the session
        ],
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

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=["i am in it", "let's just chat"],
    ):
        next_mode, carried_text = await _run_reading_partner(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert not any("word game" in line.lower() for line in tts.synthesized)
    # Only the mode's own unconditional clear-on-exit cleanup -- no
    # real game round ever ran.
    assert face.spotlights == [None]
