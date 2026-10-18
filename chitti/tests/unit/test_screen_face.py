"""Unit tests for companion_robot.device.screen_face.ScreenFaceDeviceController
(decision 0040) that hold regardless of whether pygame is actually
installed -- the graceful-degradation path. The real render-thread
lifecycle (which needs pygame importable) is in
test_screen_face_rendering.py instead, so an environment without
pygame still runs these.

Also covers decision 0044's dot-matrix expression system: _resolve_
expression() and _DiscreteTimer are pure (no pygame/rendering
involved), so they belong here too, not in the pygame-gated file.
"""
from companion_robot.device import screen_face
from companion_robot.device.interfaces import DeviceState
from companion_robot.device.screen_face import (
    _BASE_EXPRESSIONS,
    _EYE_CLOSED,
    _MOUTH_OPEN_CIRCLE,
    _DiscreteTimer,
    _build_word_timeline,
    _current_word_index,
    _resolve_expression,
    _wrap_text,
    ScreenFaceDeviceController,
)


class _FakeFont:
    """Duck-typed stand-in for a pygame.font.Font -- just enough for
    _wrap_text()/_build_word_timeline()'s own use of .size(), with no
    pygame import needed (decision 0053's own testable-without-
    hardware split, same as _resolve_expression())."""

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 10, 20)

    def get_linesize(self) -> int:
        return 20


async def test_start_without_pygame_logs_warning_and_stays_offline(monkeypatch):
    """Found during implementation: pygame has no wheel for every dev
    environment (e.g. a very new Python version with no prebuilt
    wheel yet) -- this must degrade, not crash, regardless of whether
    pygame actually happens to be installed where this test runs."""
    monkeypatch.setattr(screen_face, "_PYGAME_IMPORTED", False)
    face = ScreenFaceDeviceController()

    await face.start()

    assert face.health_check() is False
    face.set_status_led(DeviceState.LISTENING)  # must not raise even with no thread
    await face.shutdown()  # must not raise either


async def test_set_status_led_before_start_does_not_raise():
    face = ScreenFaceDeviceController()
    face.set_status_led(DeviceState.IDLE)  # just shouldn't raise


async def test_shutdown_before_start_does_not_raise():
    face = ScreenFaceDeviceController()
    await face.shutdown()  # no thread was ever spawned
    assert face.health_check() is False


def test_emergency_stop_is_synchronous_and_sets_offline():
    """Per the DeviceController ABC: must work even if the event loop
    is unresponsive -- deliberately not a coroutine. Doesn't touch
    pygame at all, so this holds with or without it installed."""
    face = ScreenFaceDeviceController()
    face._running = True  # simulate an already-running face

    face.emergency_stop()

    assert face._running is False
    assert face._get_state() == DeviceState.OFFLINE


def test_set_expression_mode_before_start_does_not_raise():
    face = ScreenFaceDeviceController()
    face.set_expression_mode("story")  # just shouldn't raise


def test_set_expression_mode_updates_stored_mode():
    face = ScreenFaceDeviceController()
    face.set_expression_mode("music")
    assert face._get_mode() == "music"


# -- _resolve_expression() (decision 0044) ---------------------------------


def test_resolve_expression_falls_back_to_base_when_no_mode_given():
    assert _resolve_expression(DeviceState.LISTENING, None) == _BASE_EXPRESSIONS[
        DeviceState.LISTENING
    ]


def test_resolve_expression_mode_override_takes_priority():
    """music overrides SPEAKING's mouth to the open-circle shape --
    the actual point of having a mode dimension at all."""
    eyes, mouth = _resolve_expression(DeviceState.SPEAKING, "music")
    assert mouth == _MOUTH_OPEN_CIRCLE


def test_resolve_expression_unmapped_mode_falls_back_to_base():
    """"story" intentionally has no PROCESSING override -- spec wants
    story to stay close to the warm default rather than a bespoke
    expression for every single (mode, state) pair."""
    assert _resolve_expression(DeviceState.PROCESSING, "story") == _BASE_EXPRESSIONS[
        DeviceState.PROCESSING
    ]


def test_resolve_expression_unknown_state_has_a_calm_default():
    assert _resolve_expression(DeviceState.OFFLINE, None) is not None


# -- _DiscreteTimer (decision 0044) -----------------------------------------


def test_discrete_timer_inactive_before_its_scheduled_time():
    timer = _DiscreteTimer(min_interval=5.0, max_interval=5.0, duration=0.2)
    assert timer.tick(0.0) is False
    assert timer.tick(4.9) is False


def test_discrete_timer_active_for_exactly_its_duration_then_resets():
    timer = _DiscreteTimer(min_interval=5.0, max_interval=5.0, duration=0.2)
    assert timer.tick(5.0) is True  # just reached -- becomes active
    assert timer.tick(5.1) is True  # still within duration
    assert timer.tick(5.2) is False  # duration elapsed -- back to inactive
    # rescheduled ~5s after the tick that ended it (5.2), not from 0
    assert timer.tick(9.0) is False
    assert timer.tick(10.2) is True


# -- set_reading_text()/set_reading_spotlight() (decision 0053) -----------


def test_set_reading_text_before_start_does_not_raise():
    face = ScreenFaceDeviceController()
    face.set_reading_text(["hello"], wpm=60.0, font_size=32, font_color="yellow")  # just shouldn't raise


def test_set_reading_text_stores_pace_size_and_color():
    face = ScreenFaceDeviceController()
    face.set_reading_text(["hello"], wpm=60.0, font_size=32, font_color="yellow")
    lines, wpm, font_size, font_color, started_at = face._get_reading_display()
    assert lines == ["hello"]
    assert wpm == 60.0
    assert font_size == 32
    assert font_color == "yellow"
    assert started_at is not None  # stamped because lines were set


def test_set_reading_text_none_clears_the_started_at_timestamp():
    face = ScreenFaceDeviceController()
    face.set_reading_text(["hello"])
    face.set_reading_text(None)
    lines, _wpm, _size, _color, started_at = face._get_reading_display()
    assert lines is None
    assert started_at is None


def test_set_reading_spotlight_before_start_does_not_raise():
    face = ScreenFaceDeviceController()
    face.set_reading_spotlight("cat")  # just shouldn't raise


def test_set_reading_spotlight_updates_stored_word():
    face = ScreenFaceDeviceController()
    face.set_reading_spotlight("cat")
    assert face._get_spotlight() == "cat"
    face.set_reading_spotlight(None)
    assert face._get_spotlight() is None


# -- _build_word_timeline() / _current_word_index() (decision 0053) -------


def test_build_word_timeline_assigns_equal_slots_in_reading_order():
    font = _FakeFont()
    lines, words = _build_word_timeline(["cat sat mat"], font, max_width=1000, seconds_per_word=0.5)

    assert lines == ["cat sat mat"]
    assert [w.text for w in words] == ["cat", "sat", "mat"]
    assert [(w.start, w.end) for w in words] == [(0.0, 0.5), (0.5, 1.0), (1.0, 1.5)]


def test_build_word_timeline_tracks_char_spans_for_a_repeated_word():
    """"the" appears twice in the same line -- char_start/char_end
    must point at each occurrence's own position, not always the
    first, so the right one highlights."""
    font = _FakeFont()
    _lines, words = _build_word_timeline(
        ["the cat and the dog"], font, max_width=1000, seconds_per_word=0.5
    )

    the_words = [w for w in words if w.text == "the"]
    assert len(the_words) == 2
    assert the_words[0].char_start == 0
    assert the_words[1].char_start == 12  # after "the cat and "


def test_build_word_timeline_wraps_long_pages_across_multiple_lines():
    font = _FakeFont()
    # Each word is 3 chars + a space = ~40px at this fake font's 10px/char;
    # max_width=35 forces a wrap after every word.
    lines, words = _build_word_timeline(["cat sat mat"], font, max_width=35, seconds_per_word=0.5)

    assert lines == ["cat", "sat", "mat"]
    assert [w.line_index for w in words] == [0, 1, 2]


def test_build_word_timeline_inserts_a_blank_separator_between_pages():
    font = _FakeFont()
    lines, words = _build_word_timeline(
        ["cat sat", "dog ran"], font, max_width=1000, seconds_per_word=0.5
    )

    assert lines == ["cat sat", "", "dog ran"]
    assert [w.line_index for w in words] == [0, 0, 2, 2]  # line 1 is the blank separator


def test_current_word_index_returns_minus_one_for_no_words():
    assert _current_word_index([], 0.0) == -1


def test_current_word_index_picks_the_word_whose_window_contains_elapsed():
    font = _FakeFont()
    _lines, words = _build_word_timeline(["cat sat mat"], font, max_width=1000, seconds_per_word=0.5)

    assert _current_word_index(words, 0.0) == 0
    assert _current_word_index(words, 0.49) == 0
    assert _current_word_index(words, 0.5) == 1
    assert _current_word_index(words, 1.4) == 2


def test_current_word_index_holds_on_the_last_word_past_total_duration():
    """So every line gets its moment on screen regardless of how long
    the child actually takes to finish reading -- never loops, never
    goes blank."""
    font = _FakeFont()
    _lines, words = _build_word_timeline(["cat sat mat"], font, max_width=1000, seconds_per_word=0.5)

    assert _current_word_index(words, 100.0) == 2
