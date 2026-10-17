"""Screen-based face display (decision 0040): a real DeviceController
implementation that renders Chitti's listening/thinking/speaking/idle
state as a simple animated face on the HDMI screen, instead of just
logging transitions like MockDeviceController does.

Adapts three hard-won, real-hardware-tested fixes from
pixel-ai/pixel_face.py, which runs this exact approach on the same Pi
1 B+ hardware class (confirmed there: "cheap enough for a 700MHz
ARMv6 core", /dev/dri/card0 present):

1. SDL has no desktop/X server to auto-detect on Pi OS Lite, so the
   video driver is tried from a fallback list rather than guessed.
2. If the kernel doesn't detect a connected display at boot, the real
   fix is `hdmi_force_hotplug=1` in config.txt -- not a driver-list
   change. Documented here so it isn't rediscovered.
3. pygame.init() opens a real ALSA audio device for pygame.mixer by
   default (unused here -- audio/real.py's arecord/aplay subprocesses
   handle all real audio), which would otherwise contend with them
   for the same device. SDL_AUDIODRIVER=dummy keeps pygame's audio
   subsystem off real hardware entirely.

pygame is imported defensively: if it's missing entirely (e.g. an
environment where the dependency didn't install) or no SDL video
driver works (no screen attached, an unexpected OS image), this logs
a warning and runs with no visible face rather than raising -- a
missing display must never be able to take down a real conversation
session.
"""
import logging
import math
import os
import threading

from .interfaces import DeviceController, DeviceState

logger = logging.getLogger(__name__)

try:
    import pygame

    _PYGAME_IMPORTED = True
except ImportError:
    pygame = None
    _PYGAME_IMPORTED = False

# See module docstring point 1.
_SDL_VIDEO_DRIVER_CANDIDATES = ("kmsdrm", "RPI", "fbcon", "fbdev", "directfb")

# See module docstring point 3. Set at import time, same as
# pixel_face.py -- this is a fixed "always dummy" default we choose
# ourselves, not read from .env, so none of decision 0016's
# import-order concerns apply here.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_FPS = 15
_EYE_GAP = 90

_BG = (10, 10, 18)
_CYAN = (0, 220, 220)
_BLUE = (40, 120, 255)
_PURPLE = (170, 90, 255)
_WHITE = (240, 240, 250)
_GREY = (90, 90, 100)
_RED = (200, 60, 60)


class ScreenFaceDeviceController(DeviceController):
    """Only set_status_led() is meant to be called from outside this
    class -- conversation/ never touches this controller at all,
    preserving the architecture's isolation requirement (the model
    has no path to device state)."""

    def __init__(self, width: int = 480, height: int = 320) -> None:
        self._width = width
        self._height = height
        self._state = DeviceState.OFFLINE
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    async def start(self) -> None:
        if self._running:
            return
        if not _PYGAME_IMPORTED:
            logger.warning("pygame is not installed -- running with no visible face")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        with self._lock:
            self._state = DeviceState.IDLE

    async def shutdown(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            self._state = DeviceState.OFFLINE

    def set_status_led(self, state: DeviceState) -> None:
        with self._lock:
            self._state = state

    def emergency_stop(self) -> None:
        """Synchronous, per the ABC's requirement -- must work even if
        the event loop is unresponsive. Safe to be this simple today:
        flipping a lock-protected flag/value, no real motor or GPIO
        involved yet."""
        self._running = False
        with self._lock:
            self._state = DeviceState.OFFLINE

    def health_check(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def _get_state(self) -> DeviceState:
        with self._lock:
            return self._state

    def _create_screen(self):
        os.environ.setdefault("SDL_FBDEV", "/dev/fb0")
        for driver in _SDL_VIDEO_DRIVER_CANDIDATES:
            os.environ["SDL_VIDEODRIVER"] = driver
            try:
                pygame.display.quit()
                pygame.display.init()
                return pygame.display.set_mode((self._width, self._height))
            except pygame.error:
                continue
        return None

    def _run(self) -> None:
        pygame.init()
        screen = self._create_screen()
        if screen is None:
            logger.warning(
                "No usable SDL video driver for the face display (tried %s) -- "
                "running without a visible face.",
                ", ".join(_SDL_VIDEO_DRIVER_CANDIDATES),
            )
            self._running = False
            return
        pygame.display.set_caption("Chitti")
        clock = pygame.time.Clock()
        t = 0.0

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False

            screen.fill(_BG)
            cx, cy = self._width // 2, self._height // 2
            state = self._get_state()
            _draw_face(screen, cx, cy, state, t)

            pygame.display.flip()
            clock.tick(_FPS)
            t += 1.0 / _FPS

        pygame.quit()


def _draw_face(screen, cx: int, cy: int, state: DeviceState, t: float) -> None:
    if state == DeviceState.LISTENING:
        pulse = 0.6 + 0.4 * abs(math.sin(t * 4))
        _draw_eyes(screen, cx, cy, _BLUE, 1.2, glow=pulse)
    elif state == DeviceState.PROCESSING:
        _draw_thinking_dots(screen, cx, cy, t)
    elif state == DeviceState.SPEAKING:
        _draw_eyes(screen, cx, cy, _WHITE, 1.0)
        _draw_mouth(screen, cx, cy + 60, t)
    elif state == DeviceState.MUTED:
        _draw_eyes(screen, cx, cy, _GREY, 0.3)
    elif state == DeviceState.ERROR:
        _draw_eyes(screen, cx, cy, _RED, 1.0)
    elif state == DeviceState.OFFLINE:
        pass  # blank screen
    else:  # IDLE (and any future state -- a calm default beats a blank/odd one)
        _draw_eyes(screen, cx, cy, _CYAN, 0.75 + 0.25 * math.sin(t * 1.5))


def _draw_eyes(screen, cx, cy, color, openness, glow=1.0):
    radius = int(28 * max(0.15, openness) * glow)
    for dx in (-_EYE_GAP // 2, _EYE_GAP // 2):
        pygame.draw.circle(screen, color, (cx + dx, cy), max(radius, 4))


def _draw_thinking_dots(screen, cx, cy, t):
    for i in range(3):
        angle = t * 4 + i * (2 * math.pi / 3)
        x = cx + int(40 * math.cos(angle))
        y = cy + int(40 * math.sin(angle))
        pygame.draw.circle(screen, _PURPLE, (x, y), 12)


def _draw_mouth(screen, cx, cy, t):
    height = int(10 + 15 * abs(math.sin(t * 8)))
    rect = pygame.Rect(cx - 40, cy - height // 2, 80, height)
    pygame.draw.ellipse(screen, _WHITE, rect)
