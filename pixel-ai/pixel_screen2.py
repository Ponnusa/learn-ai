"""Display target for pixel_visual_aid.py's rendered surfaces --
stubbed for now, no second physical screen connected yet.

Real second-screen output needs its own investigation once that
hardware exists: a second HDMI display needs the same kind of
SDL-driver-fallback debugging pixel_face.py's _create_screen() took
real hardware access to get right, AND a separate open question this
doesn't resolve yet -- whether pygame/SDL can drive two independent
display targets from one process at all, or whether screen 2 needs
its own separate process entirely. Not solvable without the actual
second screen in hand, so this isn't guessed at here.

For now: saves the surface to persona/screen2_preview.png (gitignored,
overwritten each call) so what *would* be shown can be reviewed by
pulling the file off the Pi -- verifies the rendering pipeline end to
end without needing the display hardware at all.
"""
import os

import pygame

_PREVIEW_PATH = os.path.join(os.path.dirname(__file__), "persona", "screen2_preview.png")


def show(surface: pygame.Surface) -> None:
    os.makedirs(os.path.dirname(_PREVIEW_PATH), exist_ok=True)
    pygame.image.save(surface, _PREVIEW_PATH)
