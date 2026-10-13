"""Software-only DeviceController for development without real Pi 5 +
LED + button hardware (no hardware in hand yet --
docs/decisions/0001-milestone-0-scope.md). Logs every transition
instead of touching GPIO. This is what app.py wires up today; a real
GPIO-backed implementation arrives once hardware exists.
"""
import logging

from .interfaces import DeviceController, DeviceState

logger = logging.getLogger(__name__)


class MockDeviceController(DeviceController):
    def __init__(self) -> None:
        self._running = False
        self._state = DeviceState.OFFLINE

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._state = DeviceState.IDLE
        logger.info("MockDeviceController started (no real hardware)")

    async def shutdown(self) -> None:
        self._running = False
        self._state = DeviceState.OFFLINE
        logger.info("MockDeviceController shut down")

    def set_status_led(self, state: DeviceState) -> None:
        self._state = state
        logger.info("status LED (mock) -> %s", state.value)

    def emergency_stop(self) -> None:
        self._running = False
        self._state = DeviceState.OFFLINE
        logger.warning("EMERGENCY STOP triggered (mock)")

    def health_check(self) -> bool:
        return self._running

    @property
    def state(self) -> DeviceState:
        """Test/dev hook -- not part of the DeviceController interface,
        just convenient for assertions."""
        return self._state
