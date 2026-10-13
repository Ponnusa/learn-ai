"""Chitti's application entry point (spec Milestone 1: "application
starts and shuts down cleanly"). Wires together the Device Controller
and Audio Transport -- both mocked for now, since no Pi 5 + mic +
speaker + mute-switch hardware is in hand yet
(docs/decisions/0001-milestone-0-scope.md). No conversation loop here;
that's Milestone 2+, gated on the AI backend decisions in
docs/decisions/0004-modular-pipeline-over-realtime.md.
"""
import asyncio
import logging
import signal

from companion_robot.audio.interfaces import AudioTransport
from companion_robot.audio.mock import MockAudioTransport
from companion_robot.device.interfaces import DeviceController, DeviceState
from companion_robot.device.mock import MockDeviceController
from companion_robot.diagnostics.logging_setup import configure_logging

logger = logging.getLogger(__name__)


class App:
    """Owns the top-level start/shutdown lifecycle. Milestone 1 scope
    only."""

    def __init__(self, device: DeviceController, audio: AudioTransport) -> None:
        self._device = device
        self._audio = audio
        self._running = False

    async def start(self) -> None:
        await self._device.start()
        self._device.set_status_led(
            DeviceState.MUTED if self._audio.is_muted() else DeviceState.IDLE
        )
        self._running = True
        logger.info("Chitti started")

    async def shutdown(self) -> None:
        if not self._running:
            return
        self._running = False
        await self._audio.stop_playback()
        await self._device.shutdown()
        logger.info("Chitti shut down cleanly")

    def is_running(self) -> bool:
        return self._running


async def run() -> None:
    configure_logging()
    device = MockDeviceController()
    audio = MockAudioTransport()
    app = App(device, audio)

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except (NotImplementedError, AttributeError):
            # Not available on Windows dev environments -- fine for
            # local dev; the real deployment target is Linux
            # (Raspberry Pi OS), where this works.
            pass

    await app.start()
    try:
        await stop_event.wait()
    finally:
        await app.shutdown()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
