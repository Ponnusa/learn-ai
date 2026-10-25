"""Unit tests for ScreenFaceDeviceController's real render-thread
lifecycle (decision 0040) -- needs pygame importable, so this whole
module is skipped (not failed) if it isn't. Uses SDL's own "dummy"
video driver -- a real, standard headless driver, distinct from the
production fallback list screen_face.py tries on real hardware --
so this runs without any real screen attached.
"""
import os

import pytest

pygame = pytest.importorskip("pygame")

from companion_robot.device.interfaces import DeviceState  # noqa: E402
from companion_robot.device.screen_face import ScreenFaceDeviceController  # noqa: E402


@pytest.fixture(autouse=True)
def _headless_display(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    os.environ.pop("SDL_FBDEV", None)


async def test_start_spawns_a_live_render_thread():
    face = ScreenFaceDeviceController()

    await face.start()
    try:
        assert face.health_check() is True
    finally:
        await face.shutdown()


async def test_start_is_idempotent():
    face = ScreenFaceDeviceController()
    await face.start()
    try:
        first_thread = face._thread
        await face.start()
        assert face._thread is first_thread
    finally:
        await face.shutdown()


async def test_set_status_led_updates_state():
    face = ScreenFaceDeviceController()
    await face.start()
    try:
        face.set_status_led(DeviceState.SPEAKING)
        assert face._get_state() == DeviceState.SPEAKING
    finally:
        await face.shutdown()


async def test_set_expression_mode_updates_mode_while_render_thread_is_live():
    """Decision 0044: the render thread reads _get_mode() each frame
    alongside _get_state() -- this proves the live thread doesn't
    interfere with the lock-protected value changing underneath it."""
    face = ScreenFaceDeviceController()
    await face.start()
    try:
        face.set_expression_mode("story")
        assert face._get_mode() == "story"
    finally:
        await face.shutdown()


async def test_shutdown_stops_the_thread_and_sets_offline():
    face = ScreenFaceDeviceController()
    await face.start()

    await face.shutdown()

    assert face.health_check() is False
    assert face._get_state() == DeviceState.OFFLINE


async def test_reading_text_and_spotlight_render_without_crashing_the_thread():
    """Decision 0053 (static text since decision 0088): a smoke test,
    not a pixel check -- proves the live render thread survives a
    real frame or two with the reading text active, then with the
    hint spotlight active, instead of raising inside the thread
    (which would be silent otherwise, since it's a daemon thread)."""
    import asyncio

    face = ScreenFaceDeviceController()
    await face.start()
    try:
        face.set_reading_text(
            ["The cat sat on a mat.", "The dog ran to the park."],
            font_size=28,
            font_color="yellow",
        )
        await asyncio.sleep(0.2)
        assert face.health_check() is True

        face.set_reading_spotlight("cat")
        await asyncio.sleep(0.2)
        assert face.health_check() is True

        face.set_reading_spotlight(None)
        face.set_reading_text(None)
        await asyncio.sleep(0.2)
        assert face.health_check() is True
    finally:
        await face.shutdown()


async def test_set_reading_text_highlight_wraps_a_single_position_into_a_set():
    """Decision 0112 generalized the stored highlight from one
    (sentence, word) pair to a set, for the word game's own "light up
    several words at once" case -- this proves the existing, widely-
    used single-word live-speech setter still works unchanged,
    wrapping its one position into a 1-item set."""
    face = ScreenFaceDeviceController()
    await face.start()
    try:
        face.set_reading_text_highlight("Sam", sentence_index=0, word_position=1)
        assert face._get_reading_text_highlight() == {(0, 1)}

        face.set_reading_text_highlight(None, sentence_index=0, word_position=1)
        assert face._get_reading_text_highlight() is None
    finally:
        await face.shutdown()


async def test_reading_text_with_multiple_highlights_renders_without_crashing_the_thread():
    """Decision 0112: a smoke test, not a pixel check -- same spirit
    as test_reading_text_and_spotlight_render_without_crashing_the_thread
    above, for the word game's own multi-position highlight case."""
    import asyncio

    face = ScreenFaceDeviceController()
    await face.start()
    try:
        face.set_reading_text(["S_m sat.", "A rat s_t at the mat."])
        face.set_reading_text_highlights({(0, 0), (1, 2)})
        await asyncio.sleep(0.2)
        assert face.health_check() is True

        face.set_reading_text_highlights(None)
        face.set_reading_text(None)
        await asyncio.sleep(0.2)
        assert face.health_check() is True
    finally:
        await face.shutdown()


async def test_set_reading_text_highlights_sets_multiple_positions_at_once():
    """Decision 0112: the word game's own case -- both blanked words
    highlighted in the story at the same time, not one after another."""
    face = ScreenFaceDeviceController()
    await face.start()
    try:
        face.set_reading_text_highlights({(0, 0), (1, 2)})
        assert face._get_reading_text_highlight() == {(0, 0), (1, 2)}

        face.set_reading_text_highlights(None)
        assert face._get_reading_text_highlight() is None
    finally:
        await face.shutdown()


async def test_render_thread_survives_a_bad_frame(monkeypatch):
    """Decision 0089, found live: an exception anywhere in the per-
    frame drawing code used to kill the whole render thread silently
    -- Chitti kept talking and listening fine (a separate asyncio
    loop), but the screen froze on its last good frame for the rest
    of the session, with nothing in the logs to say why. Now it's
    caught, logged, and skipped -- the thread survives and keeps
    rendering later frames."""
    import asyncio

    import companion_robot.device.screen_face as screen_face_module

    calls = {"n": 0}
    real_draw_spotlight = screen_face_module._draw_spotlight

    def _flaky_draw_spotlight(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated bad frame")
        return real_draw_spotlight(*args, **kwargs)

    monkeypatch.setattr(screen_face_module, "_draw_spotlight", _flaky_draw_spotlight)

    face = ScreenFaceDeviceController()
    await face.start()
    try:
        face.set_reading_spotlight("cat")
        await asyncio.sleep(0.3)

        assert face.health_check() is True
        # The thread kept calling it on later frames too, not just the
        # one that failed -- a true crash would have stopped at 1.
        assert calls["n"] >= 2
    finally:
        await face.shutdown()


async def test_disabled_face_still_renders_reading_text(monkeypatch):
    """Decision 0092, found live: CHITTI_DISABLE_FACE=1 used to skip
    starting the render thread entirely, so Reading Partner's own
    reading-text/spotlight/word-grid display never showed either --
    not what was asked for ("disable only face, not the display of
    words"). The thread must still run, and reading text must still
    render, with the flag set -- only the idle dot-matrix pattern is
    suppressed."""
    import asyncio

    import companion_robot.device.screen_face as screen_face_module

    monkeypatch.setattr(screen_face_module, "_FACE_DISABLED", True)

    face = ScreenFaceDeviceController()
    await face.start()
    try:
        # No spotlight/word-grid/reading-text set yet -- this is
        # exactly the state that used to draw the dot-matrix face;
        # with the flag set, it must draw nothing instead, not crash.
        await asyncio.sleep(0.2)
        assert face.health_check() is True

        face.set_reading_text(["The cat sat on a mat."], font_size=28, font_color="yellow")
        await asyncio.sleep(0.2)
        assert face.health_check() is True
    finally:
        await face.shutdown()
