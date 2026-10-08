"""Text-to-speech for Pixel: gTTS + mpg123.

gTTS stays the long-term choice even after Phase 2 hardware arrives — the
backend has no public endpoint for arbitrary-text Azure TTS, so only the
playback device changes (mpg123/headphone jack -> I2S/MAX98357A), not the
synthesis path.
"""
import os
import subprocess
import tempfile

from gtts import gTTS


def speak(text: str, lang: str = "en") -> None:
    """Synthesize text and play it back. Blocks until playback finishes."""
    if not text:
        return

    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        gTTS(text=text, lang=lang).save(path)
        # -b raises mpg123's output buffer; the Pi 1's weak audio path
        # underruns constantly with the default tiny buffer. ALSA's own
        # underrun warnings go straight to stderr regardless of -q, so
        # they're suppressed here too — they're noise, not failures.
        subprocess.run(
            ["mpg123", "-q", "-b", "2048", path],
            check=True,
            stderr=subprocess.DEVNULL,
        )
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
