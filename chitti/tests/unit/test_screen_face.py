"""Unit tests for companion_robot.device.screen_face.ScreenFaceDeviceController
(decision 0040) that hold regardless of whether pygame is actually
installed -- the graceful-degradation path. The real render-thread
lifecycle (which needs pygame importable) is in
test_screen_face_rendering.py instead, so an environment without
pygame still runs these.
"""
from companion_robot.device import screen_face
from companion_robot.device.interfaces import DeviceState
from companion_robot.device.screen_face import ScreenFaceDeviceController


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
