"""Display target for pixel_visual_aid.py's rendered surfaces --
no second physical screen connected yet.

Real second-screen output needs its own investigation once that
hardware exists: a second HDMI display needs the same kind of
SDL-driver-fallback debugging pixel_face.py's _create_screen() took
real hardware access to get right, AND a separate open question this
doesn't resolve yet -- whether pygame/SDL can drive two independent
display targets from one process at all, or whether screen 2 needs
its own separate process entirely. Not solvable without the actual
second screen in hand, so this isn't guessed at here.

Until then: shown on the existing, already-working face screen as a
temporary override (see PixelFace.show_visual()), so the rendering can
actually be seen on real hardware instead of only reviewed as a saved
PNG. Also still saves to persona/screen2_preview.png (gitignored,
overwritten each call) for review off-device.
"""
import os

import pygame

from pixel_face import face

_PREVIEW_PATH = os.path.join(os.path.dirname(__file__), "persona", "screen2_preview.png")


def show(surface: pygame.Surface) -> None:
    os.makedirs(os.path.dirname(_PREVIEW_PATH), exist_ok=True)
    pygame.image.save(surface, _PREVIEW_PATH)
    face.show_visual(surface)
