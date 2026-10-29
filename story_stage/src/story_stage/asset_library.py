"""The closed vocabulary the LLM is constrained to, and this prototype's
placeholder visuals for each value (colored shapes + a text label --
there's no real sprite art yet; swapping these for actual images later
only touches this one file, nothing in schema.py/llm.py/renderer.py
needs to change).

Keeping these as plain tuples/dicts, not an enum class, so llm.py can
drop them straight into an f-string for the system prompt without a
separate "list the enum values" step.
"""

CHARACTER_TYPES = ("dragon", "princess", "knight", "wizard", "cat", "dog")
ACTIONS = ("idle", "walk_in", "walk_out", "jump", "wave", "bounce", "sit")
MOODS = ("happy", "sad", "scared", "angry", "excited", "neutral")
BACKGROUNDS = ("forest", "castle", "beach", "night_sky", "village")

EVENT_TYPES = ("move", "speak", "jump")

CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720

# Placeholder fill color per character type -- an RGB tuple, not real
# art. First value in each enum is used as the clamp target when the
# LLM (despite the prompt's own instruction not to) returns something
# outside the vocabulary -- see schema.py's validate_scene().
CHARACTER_COLORS: dict[str, tuple[int, int, int]] = {
    "dragon": (46, 125, 70),
    "princess": (214, 97, 143),
    "knight": (120, 128, 138),
    "wizard": (111, 66, 160),
    "cat": (214, 140, 60),
    "dog": (150, 105, 70),
}

BACKGROUND_COLORS: dict[str, tuple[int, int, int]] = {
    "forest": (24, 58, 34),
    "castle": (70, 72, 82),
    "beach": (214, 196, 140),
    "night_sky": (12, 16, 48),
    "village": (92, 74, 48),
}

# A thin colored ring drawn around a character to hint at mood,
# without needing a real facial expression sprite. "neutral" draws no
# ring at all.
MOOD_RING_COLORS: dict[str, tuple[int, int, int]] = {
    "happy": (240, 200, 40),
    "sad": (70, 110, 200),
    "scared": (150, 60, 190),
    "angry": (200, 50, 40),
    "excited": (240, 120, 30),
}

DEFAULT_CHARACTER_TYPE = CHARACTER_TYPES[0]
DEFAULT_MOOD = "neutral"
DEFAULT_ACTION = "idle"
DEFAULT_BACKGROUND = BACKGROUNDS[0]
