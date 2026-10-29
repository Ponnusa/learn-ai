"""pygame-ce-style window that draws whatever SceneEngine currently
holds, every frame. No real sprite art yet (decision: see
asset_library.py's own docstring) -- each character is a colored
circle, a text label, and an optional mood ring; that's deliberately
all this needs to prove out the live-narration loop before any art is
commissioned.

Import of `pygame` is isolated to this one module -- schema.py/
llm.py/engine.py have no rendering dependency at all, so they (and
their tests) never need a display or even pygame installed.
"""
import pygame

from .asset_library import BACKGROUND_COLORS, CANVAS_HEIGHT, CANVAS_WIDTH, CHARACTER_COLORS, MOOD_RING_COLORS
from .engine import SceneEngine

_CHARACTER_RADIUS = 40
_IDLE_BACKGROUND = (18, 18, 18)
_FALLBACK_CHARACTER_COLOR = (200, 200, 200)
_LABEL_COLOR = (255, 255, 255)
_STATUS_COLOR = (240, 210, 60)
_BUBBLE_BACKGROUND = (255, 255, 255)
_BUBBLE_TEXT_COLOR = (20, 20, 20)
_BUBBLE_BORDER_COLOR = (20, 20, 20)


class SceneRenderer:
    def __init__(self, fullscreen: bool = False) -> None:
        pygame.init()
        pygame.font.init()
        flags = pygame.FULLSCREEN if fullscreen else 0
        self.screen = pygame.display.set_mode((CANVAS_WIDTH, CANVAS_HEIGHT), flags)
        pygame.display.set_caption("Story Stage")
        self._label_font = pygame.font.SysFont(None, 22)
        self._status_font = pygame.font.SysFont(None, 30)
        self._clock = pygame.time.Clock()

    def pump_events(self) -> bool:
        """Processes the window's own event queue (so it doesn't look
        hung, and so closing the window or pressing Escape actually
        works). Returns False once the caller should stop running."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
        return True

    def draw(self, engine: SceneEngine, status_text: str = "") -> None:
        scene = engine.scene
        background = BACKGROUND_COLORS.get(scene.background, _IDLE_BACKGROUND) if scene else _IDLE_BACKGROUND
        self.screen.fill(background)

        if scene is not None:
            for character in scene.characters:
                self._draw_character(engine, character)

        if status_text:
            rendered = self._status_font.render(status_text, True, _STATUS_COLOR)
            self.screen.blit(rendered, (20, 20))

        pygame.display.flip()

    def _draw_character(self, engine: SceneEngine, character) -> None:
        color = CHARACTER_COLORS.get(character.type, _FALLBACK_CHARACTER_COLOR)
        x = int(character.x)
        y = int(character.y + engine.jump_offset(character.id))

        pygame.draw.circle(self.screen, color, (x, y), _CHARACTER_RADIUS)
        ring_color = MOOD_RING_COLORS.get(character.mood)
        if ring_color is not None:
            pygame.draw.circle(self.screen, ring_color, (x, y), _CHARACTER_RADIUS + 6, width=4)

        label = self._label_font.render(f"{character.type} ({character.mood})", True, _LABEL_COLOR)
        self.screen.blit(label, (x - label.get_width() // 2, y + _CHARACTER_RADIUS + 10))

        line = engine.speech_for(character.id)
        if line:
            self._draw_speech_bubble(x, y - _CHARACTER_RADIUS - 20, line)

    def _draw_speech_bubble(self, anchor_x: int, anchor_y: int, text: str) -> None:
        padding = 10
        rendered = self._label_font.render(text, True, _BUBBLE_TEXT_COLOR)
        width = rendered.get_width() + padding * 2
        height = rendered.get_height() + padding * 2
        rect = pygame.Rect(anchor_x - width // 2, anchor_y - height, width, height)
        pygame.draw.rect(self.screen, _BUBBLE_BACKGROUND, rect, border_radius=8)
        pygame.draw.rect(self.screen, _BUBBLE_BORDER_COLOR, rect, width=2, border_radius=8)
        self.screen.blit(rendered, (rect.x + padding, rect.y + padding))

    def tick(self, fps: int = 30) -> float:
        """Caps the frame rate and returns the elapsed seconds since
        the last call (unused by SceneEngine, which reads the clock
        directly, but handy for a caller that wants it)."""
        return self._clock.tick(fps) / 1000.0

    def shutdown(self) -> None:
        pygame.quit()
