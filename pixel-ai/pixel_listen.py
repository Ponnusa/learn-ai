"""Input for Pixel: keyboard now, I2S microphone in Phase 2.

listen() is the whole interface pixel_main.py depends on, so swapping to
the ZTS6631 mic later only means rewriting this file.
"""


def listen(prompt: str = "You: ") -> str:
    """Read one line of text from the keyboard."""
    return input(prompt).strip()
