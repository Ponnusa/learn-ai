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
import time
from dataclasses import dataclass

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

# Decision 0046: how many frames between logging the rolling-average
# draw+flip duration -- ~5s of frames at _FPS, not every single frame
# (would flood the log at 15/sec). Diagnostic only, to test whether
# the heavier dot-matrix rendering (decision 0044) is contending for
# CPU with STT/TTS/API calls on the Pi 1 B+'s single weak core.
_FRAME_TIMING_LOG_INTERVAL = _FPS * 5

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


# Decision 0051: the Reading Partner mode needs the child to actually
# see story text -- nothing before this rendered any text at all, only
# the dot-matrix face. A third, independent axis alongside state/mode:
# when set_reading_text() has lines, the render loop draws them instead
# of the face for that frame; when None, the face renders as normal.
_READING_FONT_SIZE = 28
_READING_LINE_SPACING = 6
_READING_MARGIN = 16


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap to fit max_width -- simple and good enough for
    a few short decodable-story sentences, not a general text layout
    engine."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# Decision 0053: the only reading-display font colors a parent can
# choose (parent_controls/profiles.py's ChildProfile.reading_font_color),
# all legible against _BG. Cross-referenced with
# parent_controls/app.py's _VALID_READING_FONT_COLORS, which must list
# the same names.
_READING_FONT_COLORS: dict[str, tuple[int, int, int]] = {
    "white": _WHITE,
    "yellow": (240, 220, 80),
    "cyan": _CYAN,
    "green": (120, 220, 120),
}
_SPOTLIGHT_FONT_SIZE_CAP = 96
_SPOTLIGHT_FONT_SIZE_MULTIPLIER = 2
_DEFAULT_READING_WPM = 45.0


@dataclass
class TimedWord:
    """One word's slot in the teleprompter's reading timeline (decision
    0053). char_start/char_end are offsets within its own wrapped
    line's text -- tracked (rather than matching by word text) so a
    repeated word like "the" highlights the correct occurrence, not
    always the first."""

    text: str
    line_index: int
    char_start: int
    char_end: int
    start: float
    end: float


def _build_word_timeline(
    pages: list[str], font, max_width: int, seconds_per_word: float
) -> tuple[list[str], list[TimedWord]]:
    """Wraps `pages` into screen lines (reusing _wrap_text()) and
    assigns every word an equal-length time slot, in reading order
    across all lines/pages -- a uniform pace, not scaled by word
    length or punctuation (decision 0053's deferred list). Blank
    separator lines between pages take a line slot but no word/time."""
    lines: list[str] = []
    words: list[TimedWord] = []
    t = 0.0
    for page_i, page in enumerate(pages):
        for line in _wrap_text(page, font, max_width):
            line_index = len(lines)
            lines.append(line)
            cursor = 0
            for word in line.split():
                char_start = line.index(word, cursor)
                char_end = char_start + len(word)
                cursor = char_end
                words.append(
                    TimedWord(
                        text=word,
                        line_index=line_index,
                        char_start=char_start,
                        char_end=char_end,
                        start=t,
                        end=t + seconds_per_word,
                    )
                )
                t += seconds_per_word
        if page_i != len(pages) - 1:
            lines.append("")  # blank separator between pages
    return lines, words


def _current_word_index(words: list[TimedWord], elapsed: float) -> int:
    """The word whose [start, end) contains `elapsed`; holds on the
    last word once the passage's total duration has elapsed -- never
    loops, never goes blank, so every line gets its moment on screen
    regardless of how long the child takes to actually finish reading."""
    if not words:
        return -1
    for i, word in enumerate(words):
        if elapsed < word.end:
            return i
    return len(words) - 1


def _draw_teleprompter(
    screen,
    width: int,
    height: int,
    font,
    lines: list[str],
    words: list[TimedWord],
    elapsed: float,
    *,
    base_color,
    highlight_color,
    line_height: int,
) -> None:
    """Bottom-to-top auto-scroll: the current line is anchored at the
    screen's vertical middle, every other line offset by its distance
    (in lines) from it -- lines already read scroll up and off the
    top, lines not yet reached queue in from the bottom. Unlike the
    old static _draw_reading_text() this replaces, nothing is ever
    silently cut off by screen height; a line simply isn't drawn while
    it's off-screen; it gets its turn as the scroll reaches it."""
    current_idx = _current_word_index(words, elapsed)
    current_line = words[current_idx].line_index if current_idx >= 0 else 0
    anchor_y = height // 2
    for i, line in enumerate(lines):
        y = anchor_y + (i - current_line) * line_height
        if y + line_height < 0 or y > height:
            continue
        if not line:
            continue
        if current_idx >= 0 and words[current_idx].line_index == i:
            word = words[current_idx]
            prefix = line[: word.char_start]
            highlighted = line[word.char_start : word.char_end]
            suffix = line[word.char_end :]
            x = _READING_MARGIN
            if prefix:
                screen.blit(font.render(prefix, True, base_color), (x, y))
                x += font.size(prefix)[0]
            screen.blit(font.render(highlighted, True, highlight_color), (x, y))
            x += font.size(highlighted)[0]
            if suffix:
                screen.blit(font.render(suffix, True, base_color), (x, y))
        else:
            screen.blit(font.render(line, True, base_color), (_READING_MARGIN, y))


def _draw_spotlight(screen, width: int, height: int, font, word: str, color) -> None:
    """Decision 0052/0053's hint-stage fix: freezes on just the missed
    word, large and centered, so the child always knows which word is
    meant -- independent of, and drawn instead of, the scrolling
    teleprompter."""
    rendered = font.render(word, True, color)
    rect = rendered.get_rect(center=(width // 2, height // 2))
    screen.blit(rendered, rect)


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
        self._reading_lines: list[str] | None = None
        self._reading_wpm: float = _DEFAULT_READING_WPM
        self._reading_font_size: int = _READING_FONT_SIZE
        self._reading_font_color: str = "white"
        self._reading_started_at: float | None = None
        self._spotlight_word: str | None = None
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

    def set_reading_text(
        self,
        lines: list[str] | None,
        *,
        wpm: float = _DEFAULT_READING_WPM,
        font_size: int = _READING_FONT_SIZE,
        font_color: str = "white",
    ) -> None:
        """Decision 0051/0053: lines to show on screen for Reading
        Partner -- when set, the render loop draws a word-by-word-
        highlighted, auto-scrolling teleprompter instead of the dot-
        matrix face; None returns to the normal face. `wpm`/`font_size`/
        `font_color` are parent-settable (parent_controls/profiles.py's
        ChildProfile) and only take effect when `lines` is being set,
        not cleared. Independent of set_status_led()/
        set_expression_mode(), same pattern."""
        with self._lock:
            self._reading_lines = lines
            self._reading_wpm = wpm
            self._reading_font_size = font_size
            self._reading_font_color = font_color
            self._reading_started_at = time.monotonic() if lines is not None else None

    def set_reading_spotlight(self, word: str | None) -> None:
        """Decision 0053: freezes the display on a single word, large
        and centered, in the hint color -- used while Reading
        Partner's hint-and-retry loop (decision 0052) is running, so
        the child always knows which word is meant regardless of hint
        stage. Independent of set_reading_text(); None returns to
        whatever set_reading_text()/the face would otherwise show."""
        with self._lock:
            self._spotlight_word = word

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

    def _get_reading_display(
        self,
    ) -> tuple[list[str] | None, float, int, str, float | None]:
        with self._lock:
            return (
                self._reading_lines,
                self._reading_wpm,
                self._reading_font_size,
                self._reading_font_color,
                self._reading_started_at,
            )

    def _get_spotlight(self) -> str | None:
        with self._lock:
            return self._spotlight_word

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
        frame_durations: list[float] = []

        # Decision 0053: font size is now parent-configurable
        # (reading_font_size) rather than one fixed module-level font,
        # so fonts are created on demand and cached by size here --
        # local to this thread, no locking needed.
        font_cache: dict[int, "pygame.font.Font"] = {}

        def _font_for_size(size: int):
            if size not in font_cache:
                font_cache[size] = pygame.font.Font(None, size)
            return font_cache[size]

        # The word timeline only needs rebuilding when the lines/size/
        # pace actually change, not every frame at _FPS -- rebuilding
        # it 15x/second for the same unchanged passage would be wasted
        # work for no visual difference.
        timeline_key: tuple | None = None
        timeline_lines: list[str] = []
        timeline_words: list[TimedWord] = []

        while self._running:
            frame_start = time.monotonic()

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

            spotlight_word = self._get_spotlight()
            reading_lines, wpm, font_size, font_color, started_at = self._get_reading_display()

            if spotlight_word is not None:
                spotlight_size = min(_SPOTLIGHT_FONT_SIZE_CAP, font_size * _SPOTLIGHT_FONT_SIZE_MULTIPLIER)
                _draw_spotlight(
                    screen, self._width, self._height,
                    _font_for_size(spotlight_size), spotlight_word, _RED,
                )
            elif reading_lines is not None:
                reading_font = _font_for_size(font_size)
                key = (tuple(reading_lines), font_size, wpm)
                if key != timeline_key:
                    seconds_per_word = 60.0 / wpm if wpm > 0 else 60.0 / _DEFAULT_READING_WPM
                    timeline_lines, timeline_words = _build_word_timeline(
                        reading_lines, reading_font, self._width - 2 * _READING_MARGIN,
                        seconds_per_word,
                    )
                    timeline_key = key
                elapsed = time.monotonic() - started_at if started_at is not None else 0.0
                base_color = _READING_FONT_COLORS.get(font_color, _WHITE)
                # The highlighted "current" word always needs to stand
                # out from the base color too, not just the background
                # -- swaps to white in the one case (base == cyan)
                # where cyan-on-cyan would otherwise be invisible.
                highlight_color = _WHITE if base_color == _CYAN else _CYAN
                _draw_teleprompter(
                    screen, self._width, self._height, reading_font,
                    timeline_lines, timeline_words, elapsed,
                    base_color=base_color, highlight_color=highlight_color,
                    line_height=reading_font.get_linesize() + _READING_LINE_SPACING,
                )
            else:
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

            # Decision 0046: draw+flip time only -- deliberately
            # excludes clock.tick()'s own sleep, which isn't real work.
            frame_durations.append(time.monotonic() - frame_start)
            if len(frame_durations) >= _FRAME_TIMING_LOG_INTERVAL:
                avg_ms = (sum(frame_durations) / len(frame_durations)) * 1000
                logger.info(
                    "timing: face_render avg %.1fms/frame over %d frames (budget %.1fms)",
                    avg_ms,
                    len(frame_durations),
                    1000.0 / _FPS,
                )
                frame_durations.clear()

            clock.tick(_FPS)
            t += 1.0 / _FPS

        pygame.quit()
