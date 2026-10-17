"""Screen-based face display (decision 0040): a real DeviceController
implementation that renders Chitti's listening/thinking/speaking/idle
state as an animated face on the HDMI screen, instead of just logging
transitions like MockDeviceController does.

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

Decision 0044: dot-matrix expression system, replacing the original
solid-shape, continuously-pulsing face with one matching a reference
LED-dot-matrix design (circular/curved eyes and mouth made of small
individual dots) and a product-owner spec that explicitly wants
restrained, state-driven animation -- mostly-static expressions with
rare, discrete changes, never continuous pulsing/spinning/lip-sync.
Two independent axes now drive the face: the interaction state
set_status_led() already tracked (listening/thinking/speaking/idle/
...), and a new set_expression_mode() for which conversation mode is
active (story/music/learning/chat) -- e.g. STORY+SPEAKING can render
differently from CHAT+SPEAKING. set_expression_mode() is deliberately
NOT part of device/interfaces.py's DeviceController ABC: mode is a
rendering concept specific to this screen-based face, not a generic
device concept every future implementation (a real LED-matrix
controller, MockDeviceController) needs to support.
"""
import logging
import os
import random
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

_BG = (10, 10, 18)
_CYAN = (0, 220, 220)
_BLUE = (40, 120, 255)
_PURPLE = (170, 90, 255)
_WHITE = (240, 240, 250)
_GREY = (90, 90, 100)
_RED = (200, 60, 60)

# -- Dot-matrix patterns (decision 0044) -----------------------------------
# Each pattern is a small ASCII-art grid -- "#" is a lit dot, " " is
# off -- rather than raw pixel math, so they're easy to read and tweak
# by hand, the same spirit as pixel-ai's own simple shape constants.
# Rendered by _draw_pattern() below, one shared primitive for every
# eye/mouth shape instead of a bespoke draw function per shape.

_EYE_OPEN_RING = [
    "  ###  ",
    " #   # ",
    "#     #",
    "#     #",
    "#     #",
    " #   # ",
    "  ###  ",
]

_EYE_HAPPY_CURVE = [
    "       ",
    "  ###  ",
    " #   # ",
    "#     #",
    "       ",
    "       ",
    "       ",
]

_EYE_THINKING = [
    "       ",
    "   ##  ",
    "  #  # ",
    "  #  # ",
    "   ##  ",
    "       ",
    "       ",
]

_EYE_THINKING_ALT = [
    "       ",
    "  ##   ",
    " #  #  ",
    " #  #  ",
    "  ##   ",
    "       ",
    "       ",
]

_EYE_CLOSED = [
    "       ",
    "       ",
    "       ",
    " ##### ",
    "       ",
    "       ",
    "       ",
]

_MOUTH_SMILE_SMALL = [
    "       ",
    " #   # ",
    "  ###  ",
]

_MOUTH_FLAT_DOTS = [
    "       ",
    " ##### ",
    "       ",
]

_MOUTH_OPEN_CIRCLE = [
    " ### ",
    "#   #",
    " ### ",
]

# Per-DeviceState default (eyes, mouth) -- the four states the product
# spec covers (Listening/Thinking/Speaking/Idle), plus sane defaults
# for the existing Muted/Error/Offline states. Speaking's mouth is the
# same static smile as everything else: "the voice does the work, not
# the mouth" (no lip-sync, per spec).
_BASE_EXPRESSIONS: dict[DeviceState, tuple[list[str], list[str]]] = {
    DeviceState.LISTENING: (_EYE_OPEN_RING, _MOUTH_SMILE_SMALL),
    DeviceState.PROCESSING: (_EYE_THINKING, _MOUTH_FLAT_DOTS),
    DeviceState.SPEAKING: (_EYE_HAPPY_CURVE, _MOUTH_SMILE_SMALL),
    DeviceState.IDLE: (_EYE_OPEN_RING, _MOUTH_SMILE_SMALL),
    DeviceState.MUTED: (_EYE_CLOSED, _MOUTH_FLAT_DOTS),
    # Neutral and attentive, not alarming (spec: "Error/retry... no
    # alarming motion") -- same shapes as listening, just held static
    # (see _BLINK_ELIGIBLE_STATES below, which excludes ERROR).
    DeviceState.ERROR: (_EYE_OPEN_RING, _MOUTH_FLAT_DOTS),
}

# Mode-specific overrides, keyed by the mode name voice_loop_demo.py
# passes to set_expression_mode() ("story"/"music"/"learning"/"chat").
# Deliberately sparse: the spec explicitly wants story/learning/chat to
# stay close to the warm default ("the face can remain almost static
# throughout the story"); only music's mouth gets a distinct shape.
_MODE_EXPRESSIONS: dict[str, dict[DeviceState, tuple[list[str], list[str]]]] = {
    "music": {
        DeviceState.SPEAKING: (_EYE_HAPPY_CURVE, _MOUTH_OPEN_CIRCLE),
        DeviceState.LISTENING: (_EYE_OPEN_RING, _MOUTH_OPEN_CIRCLE),
        DeviceState.IDLE: (_EYE_OPEN_RING, _MOUTH_OPEN_CIRCLE),
    },
}

# Blinking is a gentle aliveness cue, not appropriate everywhere: not
# during Thinking (spec: "avoid rapid blinking" -- reserve eye changes
# there for the thinking-shift instead), and not during Muted/Error/
# Offline, which should read as calm and still.
_BLINK_ELIGIBLE_STATES = frozenset(
    {DeviceState.LISTENING, DeviceState.IDLE, DeviceState.SPEAKING}
)

_BLINK_MIN_INTERVAL = 3.0
_BLINK_MAX_INTERVAL = 6.0
_BLINK_DURATION = 0.15

_THINKING_SHIFT_MIN_INTERVAL = 2.5
_THINKING_SHIFT_MAX_INTERVAL = 4.5
_THINKING_SHIFT_DURATION = 0.4

_DOT_RADIUS = 4
_DOT_SPACING = 10
_EYE_GAP = 90
_EYE_OFFSET_Y = 20
_MOUTH_OFFSET_Y = 60

_STATE_COLORS: dict[DeviceState, tuple[int, int, int]] = {
    DeviceState.LISTENING: _BLUE,
    DeviceState.PROCESSING: _PURPLE,
    DeviceState.SPEAKING: _WHITE,
    DeviceState.MUTED: _GREY,
    DeviceState.ERROR: _RED,
}


def _resolve_expression(state: DeviceState, mode: str | None) -> tuple[list[str], list[str]]:
    """Pure lookup, no pygame/rendering involved -- testable without
    pygame installed. A mode-specific override takes priority; falls
    back to the base per-state pattern when no override exists for
    that (state, mode) pair, or when mode is None."""
    if mode is not None:
        override = _MODE_EXPRESSIONS.get(mode, {}).get(state)
        if override is not None:
            return override
    return _BASE_EXPRESSIONS.get(state, (_EYE_OPEN_RING, _MOUTH_SMILE_SMALL))


class _DiscreteTimer:
    """Tracks an occasional, discrete on/off state -- used for both
    blinking and the thinking-eye shift. Never interpolates: it's
    either in its "held" state or not, matching the product spec's
    explicit "state-driven, not timing-driven, no continuous motion"
    guidance. Pure (takes/returns plain values), so it's testable
    without pygame or real time.sleep()."""

    def __init__(self, min_interval: float, max_interval: float, duration: float) -> None:
        self._min_interval = min_interval
        self._max_interval = max_interval
        self._duration = duration
        self._next_at = random.uniform(min_interval, max_interval)
        self._active_until: float | None = None

    def tick(self, t: float) -> bool:
        if self._active_until is not None:
            if t < self._active_until:
                return True
            self._active_until = None
            self._next_at = t + random.uniform(self._min_interval, self._max_interval)
            return False
        if t >= self._next_at:
            self._active_until = t + self._duration
            return True
        return False


def _draw_pattern(screen, cx: int, cy: int, pattern: list[str], color) -> None:
    width = len(pattern[0])
    height = len(pattern)
    for row_i, row in enumerate(pattern):
        for col_i, cell in enumerate(row):
            if cell != "#":
                continue
            x = cx + (col_i - (width - 1) / 2) * _DOT_SPACING
            y = cy + (row_i - (height - 1) / 2) * _DOT_SPACING
            pygame.draw.circle(screen, color, (int(x), int(y)), _DOT_RADIUS)


class ScreenFaceDeviceController(DeviceController):
    """set_status_led() and set_expression_mode() are the only methods
    meant to be called from outside this class -- conversation/ never
    touches this controller at all, preserving the architecture's
    isolation requirement (the model has no path to device state)."""

    def __init__(self, width: int = 480, height: int = 320) -> None:
        self._width = width
        self._height = height
        self._state = DeviceState.OFFLINE
        self._mode: str | None = None
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

    def set_expression_mode(self, mode: str | None) -> None:
        """Which conversation mode is active ("story"/"music"/
        "learning"/"chat"/None), independent of the interaction state
        set_status_led() tracks -- decision 0044."""
        with self._lock:
            self._mode = mode

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

    def _get_mode(self) -> str | None:
        with self._lock:
            return self._mode

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
        blinker = _DiscreteTimer(_BLINK_MIN_INTERVAL, _BLINK_MAX_INTERVAL, _BLINK_DURATION)
        thinking_shifter = _DiscreteTimer(
            _THINKING_SHIFT_MIN_INTERVAL, _THINKING_SHIFT_MAX_INTERVAL, _THINKING_SHIFT_DURATION
        )

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False

            screen.fill(_BG)
            cx, cy = self._width // 2, self._height // 2
            state = self._get_state()

            if state == DeviceState.OFFLINE:
                pygame.display.flip()
                clock.tick(_FPS)
                t += 1.0 / _FPS
                continue

            mode = self._get_mode()
            eye_pattern, mouth_pattern = _resolve_expression(state, mode)

            # Discrete, restrained animation only -- per spec, never
            # continuous pulsing/spinning/lip-sync.
            if state in _BLINK_ELIGIBLE_STATES and blinker.tick(t):
                eye_pattern = _EYE_CLOSED
            elif state == DeviceState.PROCESSING and thinking_shifter.tick(t):
                eye_pattern = _EYE_THINKING_ALT

            color = _STATE_COLORS.get(state, _CYAN)
            eye_y = cy - _EYE_OFFSET_Y
            _draw_pattern(screen, cx - _EYE_GAP // 2, eye_y, eye_pattern, color)
            _draw_pattern(screen, cx + _EYE_GAP // 2, eye_y, eye_pattern, color)
            _draw_pattern(screen, cx, cy + _MOUTH_OFFSET_Y, mouth_pattern, _WHITE)

            pygame.display.flip()
            clock.tick(_FPS)
            t += 1.0 / _FPS

        pygame.quit()
