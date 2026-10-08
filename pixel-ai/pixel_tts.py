"""Text-to-speech for Pixel.

Two paths:
- speak_reply_audio(): plays audio already synthesized by the backend's
  /api/chat/messages/{id}/audio endpoint — the same one the LearnX web
  app's "read aloud" button uses. It runs the message through GPT-4o-mini
  first to strip LaTeX/markdown into natural spoken prose, so this is the
  only path that pronounces formulas correctly instead of reading out
  literal asterisks and dollar signs.
- speak(): gTTS, for short ad-hoc phrases that never go through chat/send
  and so have no message_id to fetch backend audio for (status updates,
  the game stub, etc).
"""
import os
import subprocess
import tempfile

from gtts import gTTS


def _play_file(path: str) -> None:
    # -b raises mpg123's output buffer; the Pi 1's weak audio path
    # underruns constantly with the default tiny buffer. ALSA's own
    # underrun warnings go straight to stderr regardless of -q, so
    # they're suppressed here too — they're noise, not failures.
    subprocess.run(
        ["mpg123", "-q", "-b", "2048", path],
        check=True,
        stderr=subprocess.DEVNULL,
    )


def speak(text: str, lang: str = "en") -> None:
    """Synthesize local text with gTTS and play it. Blocks until done."""
    if not text:
        return

    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        gTTS(text=text, lang=lang).save(path)
        _play_file(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def speak_reply_audio(audio_bytes: bytes) -> None:
    """Play already-synthesized mp3 bytes from the backend. Blocks until done."""
    if not audio_bytes:
        return

    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(audio_bytes)
        _play_file(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
