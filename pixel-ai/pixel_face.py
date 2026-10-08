"""Pixel's face: pygame animations on HDMI for 5 states.

Runs its own render loop on a background thread so the rest of Pixel
(keyboard input, API calls) can block without freezing the face. Phase 2
swaps the render target to the ST7789 display; callers only ever touch
set_state(), never pygame directly.
"""
import logging
import math
import os
import threading
import time

import pygame

logger = logging.getLogger(__name__)

# Pi OS Lite has no desktop/X server, so SDL's default driver probe
# (wayland/x11/kmsdrm) fails with "EGL not initialized". Try raw
# framebuffer drivers first instead. Which name actually works depends on
# the SDL2 build on a given Pi OS image, so we try each in turn rather
# than guessing one.
_SDL_VIDEO_DRIVER_CANDIDATES = ("fbcon", "fbdev", "kmsdrm", "directfb")

# pygame.init() also opens an ALSA audio device for pygame.mixer, which we
# never use (gTTS + mpg123 handle all audio) — left alone, it fights
# mpg123 for the same device and spams ALSA underrun warnings continuously,
# even when nothing is being spoken. The dummy driver keeps SDL's audio
# subsystem from touching real hardware at all.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

STATE_IDLE = "idle"
STATE_LISTENING = "listening"
STATE_THINKING = "thinking"
STATE_TALKING = "talking"
STATE_HAPPY = "happy"

_BG = (10, 10, 18)
_CYAN = (0, 220, 220)
_BLUE = (40, 120, 255)
_PURPLE = (170, 90, 255)
_WHITE = (240, 240, 250)

_FPS = 15
_EYE_GAP = 90


class PixelFace:
    """Single shared face instance, cheap enough for a 700MHz ARMv6 core."""

    def __init__(self, width: int = 480, height: int = 320):
        self._width = width
        self._height = height
        self._state = STATE_IDLE
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def set_state(self, state: str) -> None:
        with self._lock:
            self._state = state

    def _get_state(self) -> str:
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
                "No usable SDL video driver for the face display (tried %s) — "
                "running without a visible face.",
                ", ".join(_SDL_VIDEO_DRIVER_CANDIDATES),
            )
            self._running = False
            return
        pygame.display.set_caption("Pixel")
        clock = pygame.time.Clock()
        t = 0.0

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False

            screen.fill(_BG)
            state = self._get_state()
            cx, cy = self._width // 2, self._height // 2

            if state == STATE_IDLE:
                self._draw_eyes(screen, cx, cy, _CYAN, 0.75 + 0.25 * math.sin(t * 1.5))
            elif state == STATE_LISTENING:
                pulse = 0.6 + 0.4 * abs(math.sin(t * 4))
                self._draw_eyes(screen, cx, cy, _BLUE, 1.2, glow=pulse)
            elif state == STATE_THINKING:
                self._draw_thinking_dots(screen, cx, cy, t)
            elif state == STATE_TALKING:
                self._draw_eyes(screen, cx, cy, _WHITE, 1.0)
                self._draw_mouth(screen, cx, cy + 60, t)
            elif state == STATE_HAPPY:
                self._draw_happy(screen, cx, cy, t)

            pygame.display.flip()
            clock.tick(_FPS)
            t += 1.0 / _FPS

        pygame.quit()

    def _draw_eyes(self, screen, cx, cy, color, openness, glow=1.0):
        radius = int(28 * max(0.15, openness) * glow)
        for dx in (-_EYE_GAP // 2, _EYE_GAP // 2):
            pygame.draw.circle(screen, color, (cx + dx, cy), max(radius, 4))

    def _draw_thinking_dots(self, screen, cx, cy, t):
        for i in range(3):
            angle = t * 4 + i * (2 * math.pi / 3)
            x = cx + int(40 * math.cos(angle))
            y = cy + int(40 * math.sin(angle))
            pygame.draw.circle(screen, _PURPLE, (x, y), 12)

    def _draw_mouth(self, screen, cx, cy, t):
        height = int(10 + 15 * abs(math.sin(t * 8)))
        rect = pygame.Rect(cx - 40, cy - height // 2, 80, height)
        pygame.draw.ellipse(screen, _WHITE, rect)

    def _draw_happy(self, screen, cx, cy, t):
        for dx in (-_EYE_GAP // 2, _EYE_GAP // 2):
            rect = pygame.Rect(cx + dx - 25, cy - 15, 50, 30)
            pygame.draw.arc(screen, _CYAN, rect, math.pi, 2 * math.pi, 6)
        for i in range(6):
            angle = t * 2 + i * (math.pi / 3)
            x = cx + int(110 * math.cos(angle))
            y = cy + int(90 * math.sin(angle))
            pygame.draw.circle(screen, _WHITE, (x, y), 3)


face = PixelFace()
