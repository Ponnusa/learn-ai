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
