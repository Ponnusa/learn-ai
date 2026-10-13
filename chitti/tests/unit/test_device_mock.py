"""Unit tests for companion_robot.device.mock.MockDeviceController --
Milestone 1. No real hardware -- see docs/decisions/0001-milestone-0-
scope.md for why this is mocked, not GPIO-backed, at this stage.
"""
from companion_robot.device.interfaces import DeviceState
from companion_robot.device.mock import MockDeviceController


async def test_start_brings_device_to_idle():
    device = MockDeviceController()
    assert device.health_check() is False
    await device.start()
    assert device.health_check() is True
    assert device.state == DeviceState.IDLE


async def test_shutdown_is_safe_even_if_never_started():
    device = MockDeviceController()
    await device.shutdown()  # must not raise
    assert device.health_check() is False
    assert device.state == DeviceState.OFFLINE


async def test_shutdown_after_start():
    device = MockDeviceController()
    await device.start()
    await device.shutdown()
    assert device.health_check() is False
    assert device.state == DeviceState.OFFLINE


async def test_set_status_led_updates_state():
    device = MockDeviceController()
    await device.start()
    device.set_status_led(DeviceState.LISTENING)
    assert device.state == DeviceState.LISTENING


def test_emergency_stop_is_synchronous_and_forces_offline():
    device = MockDeviceController()
    device.emergency_stop()  # must work without start() ever being awaited
    assert device.health_check() is False
    assert device.state == DeviceState.OFFLINE
