"""Unit tests for companion_robot.app.App -- Milestone 1's "application
starts and shuts down cleanly" acceptance criterion. No real hardware --
uses the mocked Device Controller and Audio Transport.
"""
from companion_robot.app import App
from companion_robot.device.interfaces import DeviceState
from companion_robot.device.mock import MockDeviceController
from companion_robot.audio.mock import MockAudioTransport


async def test_start_brings_device_online_and_sets_idle_led():
    device = MockDeviceController()
    audio = MockAudioTransport()
    app = App(device, audio)

    await app.start()

    assert app.is_running() is True
    assert device.health_check() is True
    assert device.state == DeviceState.IDLE


async def test_start_reflects_mute_state_on_led():
    device = MockDeviceController()
    audio = MockAudioTransport()
    audio.set_muted(True)
    app = App(device, audio)

    await app.start()

    assert device.state == DeviceState.MUTED


async def test_shutdown_stops_playback_and_powers_down_device():
    device = MockDeviceController()
    audio = MockAudioTransport()
    app = App(device, audio)

    await app.start()
    await app.shutdown()

    assert app.is_running() is False
    assert device.health_check() is False
    assert device.state == DeviceState.OFFLINE


async def test_shutdown_is_safe_to_call_without_start():
    device = MockDeviceController()
    audio = MockAudioTransport()
    app = App(device, audio)

    await app.shutdown()  # must not raise

    assert app.is_running() is False
