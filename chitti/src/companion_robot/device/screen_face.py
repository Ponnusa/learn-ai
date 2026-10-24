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

# Decision 0092: CHITTI_DISABLE_FACE=1 suppresses only the idle
# dot-matrix face pattern (the render loop's "else" branch below) --
# an A/B toggle for isolating that pattern-drawing work's own cost.
# Reading Partner's own reading-text/spotlight/word-grid display are
# unaffected either way; they're a different branch of the same loop,
# and the loop itself still runs regardless of this flag.
_FACE_DISABLED = os.environ.get("CHITTI_DISABLE_FACE") == "1"

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
# No longer read by the render loop (decision 0088 removed the paced
# auto-scroll) -- kept only as set_reading_text()'s/__init__'s default
# for `wpm`, which parent_controls' reading_pace_wpm setting still
# writes through unchanged, so neither needs to change.
_DEFAULT_READING_WPM = 45.0


def _draw_reading_lines_static(
    screen, width: int, height: int, font, lines: list[tuple[int, int, str]], color, line_height: int,
    highlight: tuple[int, int] | None = None, highlight_color=_RED,
) -> None:
    """Decision 0088: shows the sentence as plain, static text while
    Chitti reads it -- no moving/scrolling teleprompter. Replaces the
    old timed auto-scroll (decision 0053), which tracked a simulated
    reading pace rather than the real audio, and which a product-
    owner report found going fully blank partway through a session on
    real hardware (traced to set_reading_text()'s own clock starting
    well before the text it was timing actually got read -- see
    decision 0086's note; removing the clock dependency entirely
    removes that whole class of bug, not just the one instance of it
    already fixed). Centered as one block vertically, and -- decision
    0093, now that this runs on a TV over HDMI, with enough room to
    show the whole story rather than cycling one sentence at a time --
    each line centered horizontally too, instead of pinned to the
    left margin.

    Decision 0098: `lines` triples each wrapped display line with
    the index of the original sentence ("page") it came from and
    that line's own starting word position within that sentence, and
    `highlight`, when given, is `(sentence_index, word_position)` --
    matched by POSITION, not word text. Found live, twice: (1)
    without the sentence-index scoping, highlighting "Sam" while
    reading "Sam can nap." (sentence 3 of "Sam and the Cat") also lit
    up "Sam" in sentence 1 and sentence 4, since the whole story is
    shown on screen at once and the word alone is ambiguous between
    sentences that reuse it; (2) even WITHIN one sentence, matching
    by word text lit up BOTH "and"s in "Pat and the pup run and
    run." the moment the FIRST one was being spoken, since a repeated
    word is just as ambiguous within a single sentence as across
    sentences. Matching by position (this word is the Nth word of
    this sentence) rather than by text has no such ambiguity, however
    many times a word repeats. The text itself never moves or
    scrolls, only a word's own color changes, so this stays immune to
    decision 0088's own reason the old teleprompter was removed. The
    caller is responsible for updating `highlight` in real time
    against REAL audio timestamps (reading/word_timing.py), not a
    guessed pace -- this function only draws whatever it's told, each
    frame."""
    visible = [(idx, offset, line) for idx, offset, line in lines if line]
    total_height = len(visible) * line_height
    start_y = max(0, (height - total_height) // 2)
    space_width = font.size(" ")[0]
    target_sentence, target_position = highlight if highlight is not None else (None, None)
    for i, (sentence_index, word_offset, line) in enumerate(visible):
        line_width = font.size(line)[0]
        x = max(_READING_MARGIN, (width - line_width) // 2)
        y = start_y + i * line_height
        if target_sentence is None or sentence_index != target_sentence:
            screen.blit(font.render(line, True, color), (x, y))
            continue
        for j, word in enumerate(line.split(" ")):
            word_color = highlight_color if word_offset + j == target_position else color
            rendered = font.render(word, True, word_color)
            screen.blit(rendered, (x, y))
            x += rendered.get_width() + space_width


def _draw_spotlight(screen, width: int, height: int, font, word: str, color) -> None:
    """Decision 0052/0053's hint-stage fix: freezes on just the missed
    word, large and centered, so the child always knows which word is
    meant -- independent of, and drawn instead of, the scrolling
    teleprompter."""
    rendered = font.render(word, True, color)
    rect = rendered.get_rect(center=(width // 2, height // 2))
    screen.blit(rendered, rect)


# Decision 0084: word-family practice used to ask one word at a time,
# each needing its own capture -- found slow and repetitive live. Now
# every candidate is shown at once, in its own block, so the child can
# read straight through them in one take (voice_loop_demo.py captures
# once against the whole set). 1-2 words keep one column (bigger
# boxes, nothing to wrap to); 3+ wrap to two columns, same spirit as
# _wrap_text()'s own "simple and good enough" bar -- this never needs
# to lay out more than word_family.py's own num_words default (4).
_WORD_GRID_MARGIN = 20
_WORD_GRID_GAP = 16
_WORD_GRID_FONT_SIZE = 40
_WORD_GRID_BOX_COLOR = _BLUE
_WORD_GRID_BORDER_COLOR = _WHITE
_WORD_GRID_BORDER_WIDTH = 3
_WORD_GRID_BORDER_RADIUS = 14
# Decision 0095: the word Chitti is actively speaking during
# word-family modeling gets a distinct box color + thicker border,
# so it's visually obvious which word is "live" without hiding the
# rest of the grid (set_reading_spotlight() would hide the others).
_WORD_GRID_HIGHLIGHT_BOX_COLOR = _RED
_WORD_GRID_HIGHLIGHT_BORDER_WIDTH = 6


def _draw_word_grid(
    screen, width: int, height: int, font, words: list[str], highlight: str | None = None,
) -> None:
    columns = 1 if len(words) <= 2 else 2
    rows = -(-len(words) // columns)  # ceil division
    box_w = (width - 2 * _WORD_GRID_MARGIN - (columns - 1) * _WORD_GRID_GAP) // columns
    box_h = (height - 2 * _WORD_GRID_MARGIN - (rows - 1) * _WORD_GRID_GAP) // rows
    for i, word in enumerate(words):
        row, col = divmod(i, columns)
        x = _WORD_GRID_MARGIN + col * (box_w + _WORD_GRID_GAP)
        y = _WORD_GRID_MARGIN + row * (box_h + _WORD_GRID_GAP)
        rect = pygame.Rect(x, y, box_w, box_h)
        is_highlighted = highlight is not None and word == highlight
        box_color = _WORD_GRID_HIGHLIGHT_BOX_COLOR if is_highlighted else _WORD_GRID_BOX_COLOR
        border_width = (
            _WORD_GRID_HIGHLIGHT_BORDER_WIDTH if is_highlighted else _WORD_GRID_BORDER_WIDTH
        )
        pygame.draw.rect(screen, box_color, rect, border_radius=_WORD_GRID_BORDER_RADIUS)
        pygame.draw.rect(
            screen, _WORD_GRID_BORDER_COLOR, rect,
            width=border_width, border_radius=_WORD_GRID_BORDER_RADIUS,
        )
        rendered = font.render(word, True, _WHITE)
        screen.blit(rendered, rendered.get_rect(center=rect.center))


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
        self._word_grid: list[str] | None = None
        self._word_grid_highlight: str | None = None
        self._reading_text_highlight: tuple[int, int] | None = None
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
        Partner -- when set, the render loop draws them as plain,
        centered static text instead of the dot-matrix face; None
        returns to the normal face. Decision 0088 removed the earlier
        word-by-word-highlighted auto-scroll (it tracked a simulated
        reading pace, not the real audio, and a bad frame anywhere in
        it could silently kill the whole render thread for the rest of
        a session) -- `wpm` is accepted for backward compatibility
        with existing callers and parent_controls' reading_pace_wpm
        setting, but no longer affects what's drawn. `font_size`/
        `font_color` are parent-settable (parent_controls/profiles.py's
        ChildProfile) and only take effect when `lines` is being set,
        not cleared. Independent of set_status_led()/
        set_expression_mode(), same pattern.

        Decision 0093: logs whatever's being shown (or that it was
        cleared) -- found live, debugging a real session, that there
        was no way to tell from the console/logs alone what the
        screen actually had on it at any given moment, on real
        hardware where watching the screen directly isn't always
        practical while reading a log back afterward."""
        logger.info("reading text: %s", lines if lines is not None else "(cleared)")
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
        logger.info("reading spotlight: %s", word if word is not None else "(cleared)")
        with self._lock:
            self._spotlight_word = word

    def set_word_grid(self, words: list[str] | None) -> None:
        """Decision 0084: all of a word-family set's candidates at
        once, each in its own block -- drawn instead of the spotlight/
        teleprompter/face while set, same independent-state pattern as
        set_reading_spotlight(). None returns to whatever else would
        otherwise show."""
        logger.info("word grid: %s", words if words is not None else "(cleared)")
        with self._lock:
            self._word_grid = words

    def set_word_grid_highlight(self, word: str | None) -> None:
        """Decision 0095: marks which word in the current grid Chitti
        is actively speaking, so modeling a word family highlights
        each word in turn instead of leaving the whole grid static
        throughout. Independent of set_word_grid() itself -- the
        grid's own words don't change, just which one is picked out."""
        logger.info("word grid highlight: %s", word if word is not None else "(cleared)")
        with self._lock:
            self._word_grid_highlight = word

    def set_reading_text_highlight(
        self, word: str | None, sentence_index: int | None, word_position: int | None = None,
    ) -> None:
        """Decision 0098: marks which word in the current reading
        text Chitti is actively speaking, driven by real audio
        timestamps (reading/word_timing.py) rather than a simulated
        pace. Matched by `(sentence_index, word_position)` -- the
        Nth word of the Mth sentence on screen -- not by the word's
        own text. Found live, twice: a word repeated across
        sentences (e.g. "Sam" in both sentence 1 and sentence 3) lit
        up in EVERY sentence containing it; a word repeated WITHIN
        one sentence (e.g. both "and"s in "Pat and the pup run and
        run.") lit up both at once the moment the first was spoken.
        Position has neither ambiguity, however many times a word
        repeats; see _draw_reading_lines_static()'s own docstring.
        `word` is accepted only for the log line's own readability --
        matching itself never looks at it. Independent of
        set_reading_text() itself -- the text doesn't change or
        move, just which word's color is picked out."""
        logger.info(
            "reading text highlight: %s (sentence %s, word %s)",
            word if word is not None else "(cleared)", sentence_index, word_position,
        )
        with self._lock:
            self._reading_text_highlight = (
                (sentence_index, word_position) if word is not None else None
            )

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

    def _get_word_grid(self) -> list[str] | None:
        with self._lock:
            return self._word_grid

    def _get_word_grid_highlight(self) -> str | None:
        with self._lock:
            return self._word_grid_highlight

    def _get_reading_text_highlight(self) -> tuple[int, int] | None:
        with self._lock:
            return self._reading_text_highlight

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
        # Decision 0053: font size is now parent-configurable
        # (reading_font_size) rather than one fixed module-level font,
        # so fonts are created on demand and cached by size here --
        # local to this thread, no locking needed.
        font_cache: dict[int, "pygame.font.Font"] = {}

        def _font_for_size(size: int):
            if size not in font_cache:
                font_cache[size] = pygame.font.Font(None, size)
            return font_cache[size]

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

            spotlight_word = self._get_spotlight()
            word_grid = self._get_word_grid()
            word_grid_highlight = self._get_word_grid_highlight()
            reading_text_highlight = self._get_reading_text_highlight()
            # wpm/started_at are still stored by set_reading_text() (so
            # existing callers and parent_controls' reading_pace_wpm
            # setting don't need to change), but decision 0088's static
            # text no longer needs either -- nothing left to pace or
            # time here.
            reading_lines, _wpm, font_size, font_color, _started_at = self._get_reading_display()

            try:
                if spotlight_word is not None:
                    spotlight_size = min(
                        _SPOTLIGHT_FONT_SIZE_CAP, font_size * _SPOTLIGHT_FONT_SIZE_MULTIPLIER
                    )
                    _draw_spotlight(
                        screen, self._width, self._height,
                        _font_for_size(spotlight_size), spotlight_word, _RED,
                    )
                elif word_grid is not None:
                    _draw_word_grid(
                        screen, self._width, self._height,
                        _font_for_size(_WORD_GRID_FONT_SIZE), word_grid,
                        highlight=word_grid_highlight,
                    )
                elif reading_lines is not None:
                    reading_font = _font_for_size(font_size)
                    # Decision 0098: each wrapped display line keeps
                    # the index of the original sentence ("page") it
                    # came from, AND its own starting word position
                    # within that sentence -- so a highlight can be
                    # scoped to one exact (sentence, word) position,
                    # not just a sentence plus the word's own text
                    # (ambiguous when a word repeats within the same
                    # sentence) -- see _draw_reading_lines_static()'s
                    # own docstring.
                    wrapped_lines: list[tuple[int, int, str]] = []
                    for page_index, page in enumerate(reading_lines):
                        word_offset = 0
                        for line in _wrap_text(
                            page, reading_font, self._width - 2 * _READING_MARGIN
                        ):
                            wrapped_lines.append((page_index, word_offset, line))
                            word_offset += len(line.split(" "))
                    base_color = _READING_FONT_COLORS.get(font_color, _WHITE)
                    _draw_reading_lines_static(
                        screen, self._width, self._height, reading_font, wrapped_lines, base_color,
                        line_height=reading_font.get_linesize() + _READING_LINE_SPACING,
                        highlight=reading_text_highlight,
                    )
                elif not _FACE_DISABLED:
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
            except Exception:
                # Decision 0089, found live: an unhandled exception
                # anywhere in this block used to kill this whole
                # daemon thread silently -- Chitti kept talking and
                # listening fine (a separate asyncio loop), but the
                # screen froze on its last good frame for the rest of
                # the session, with nothing in the logs to say why.
                # Same "a display problem must never take down a real
                # conversation session" principle the module docstring
                # already states for a missing driver -- just not
                # previously applied to a frame that's already
                # rendering. Logged once per bad frame (cheap
                # insurance against a log-spam loop) and the thread
                # keeps going, so it recovers on its own as soon as
                # the content changes to something that doesn't fail.
                logger.exception("face render thread: frame failed, skipping it")

            pygame.display.flip()

            clock.tick(_FPS)
            t += 1.0 / _FPS

        pygame.quit()
