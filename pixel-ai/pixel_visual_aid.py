"""Renders visual aids for the premium Realtime tier's show_formula/
show_counting_visual tools (see pixel_openai_voice_semantic.py) --
rendering only, no display and no hardware dependency, so both
functions here are testable without any screen attached.

Deliberately NOT using Manim (the technology behind LearnX's own
video-generation pipeline) -- Manim renders offline, taking ~60s per
clip, far too slow to appear *while* Pixel is still talking. These
produce a single static image, fast enough to show alongside live
narration instead of as a separate async job.

render_formula() uses matplotlib's `mathtext` engine -- it understands
basic LaTeX-like math syntax ($...$, superscripts, fractions) without
needing a full TeX installation, which would be far too heavy for this
project's hardware targets.

render_counting_visual() is plain pygame drawing (circles, text) --
the same cheap primitive-shape technique already proven to work on
weak hardware in pixel_face.py, not a new rendering technology.
Generic over `object_label` (apples, fingers, dots, anything) rather
than needing per-object icon artwork.
"""
import io

import pygame
from matplotlib.figure import Figure

_BG = (255, 255, 255)
_FG = (20, 20, 30)
_CIRCLE_RADIUS = 18
_CIRCLE_GAP = 10


def render_formula(latex: str, font_size: int = 32) -> pygame.Surface:
    """`latex` should be wrapped in $...$ for math rendering (matplotlib's
    mathtext convention), e.g. "$2+2=4$" or "$F=ma$". Returns a pygame
    Surface sized to fit the rendered text, white background."""
    fig = Figure(figsize=(4, 1.2), dpi=100, facecolor="white")
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(0.5, 0.5, latex, fontsize=font_size, ha="center", va="center")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.2)
    buf.seek(0)
    return pygame.image.load(buf, "formula.png")


def render_counting_visual(
    count_a: int, count_b: int, operation: str, object_label: str,
) -> pygame.Surface:
    """Draws count_a circles, an operation symbol (+/-), count_b
    circles, '=', and the result as both a number and that many
    circles, with object_label captioned underneath -- e.g.
    render_counting_visual(2, 2, "+", "apples") for "2 apples + 2
    apples = 4 apples"."""
    result = count_a + count_b if operation == "+" else count_a - count_b
    groups = [count_a, count_b, max(result, 0)]
    symbols = [operation, "="]

    group_width = max(groups) * (2 * _CIRCLE_RADIUS + _CIRCLE_GAP)
    width = group_width * 3 + 200  # room for the two symbols between groups
    height = 2 * _CIRCLE_RADIUS + 80  # room for the caption text below

    surface = pygame.Surface((width, height))
    surface.fill(_BG)
    font = pygame.font.SysFont(None, 36)

    x = 20
    cy = height // 2 - 20
    for i, count in enumerate(groups):
        for n in range(count):
            cx = x + n * (2 * _CIRCLE_RADIUS + _CIRCLE_GAP) + _CIRCLE_RADIUS
            pygame.draw.circle(surface, _FG, (cx, cy), _CIRCLE_RADIUS)
        group_px_width = max(count, 1) * (2 * _CIRCLE_RADIUS + _CIRCLE_GAP)
        x += group_px_width + 20
        if i < len(symbols):
            sym_surface = font.render(symbols[i], True, _FG)
            surface.blit(sym_surface, (x, cy - sym_surface.get_height() // 2))
            x += sym_surface.get_width() + 20

    caption = f"{count_a} {object_label} {operation} {count_b} {object_label} = {result} {object_label}"
    caption_surface = font.render(caption, True, _FG)
    surface.blit(caption_surface, (20, height - 50))

    return surface
