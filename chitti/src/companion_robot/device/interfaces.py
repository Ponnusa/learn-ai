"""Typed interface for the Device Controller (spec section 3.2.A).

Milestone 1: MockDeviceController (mock.py) is the first real
implementation -- software-only, since no Pi 5 + LED + button hardware
is in hand yet (docs/decisions/0001-milestone-0-scope.md).
"""
from abc import ABC, abstractmethod
from enum import Enum


class DeviceState(str, Enum):
    """The states spec section 4 requires the system to distinguish:
    listening, processing, speaking, muted, and offline. IDLE and ERROR
    added for the resting state between turns and for a visible failure
    indicator, respectively."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    MUTED = "muted"
    OFFLINE = "offline"
    ERROR = "error"


class DeviceController(ABC):
    """Owns hardware startup/shutdown, the status LED, watchdog health,
    and emergency-stop (spec section 3.2.A).

    Physically isolated from companion_robot.conversation -- no code
    path lets a model response or tool call reach this interface
    (docs/architecture.md's Safety boundary section; spec core
    principle 6: the robot must never rely on cloud AI to stop a motor
    or execute an emergency stop).
    """

    @abstractmethod
    async def start(self) -> None:
        """Brings hardware online. Must raise on failure, not silently
        no-op -- callers need to know startup didn't actually succeed."""
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanly powers down hardware. Must be safe to call even if
        start() never completed or was never called."""
        raise NotImplementedError

    @abstractmethod
    def set_status_led(self, state: DeviceState) -> None:
        """Reflects the current device state visibly (spec section 4)."""
        raise NotImplementedError

    @abstractmethod
    def emergency_stop(self) -> None:
        """Local, synchronous, hardware-level stop. Must work even if
        the AI backend, network, or event loop is unresponsive -- this
        is why it's synchronous, not a coroutine someone could forget
        to await."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Watchdog probe -- True if the device's own local subsystems
        are responsive. Deliberately does not check network or AI
        backend reachability; that's a separate concern (spec section
        9's offline/degraded-mode handling), not local hardware health."""
        raise NotImplementedError
