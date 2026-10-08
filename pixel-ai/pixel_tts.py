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
    #
    # stdin=DEVNULL is the important one: mpg123 grabs the controlling
    # terminal for its own interactive keyboard controls (pause/seek/quit)
    # whenever its stdin is a real TTY. That steals every keystroke while
    # it's playing, and killing it mid-playback (stop()) doesn't give it
    # a chance to restore the terminal afterward — breaking input() even
    # once playback is over. Feeding it /dev/null means it never touches
    # the terminal's input at all, no matter how it's threaded.
    subprocess.run(
        ["mpg123", "-q", "-b", "2048", path],
        check=True,
        stdin=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _play_file_async(path: str) -> subprocess.Popen:
    return subprocess.Popen(
        ["mpg123", "-q", "-b", "2048", path],
        stdin=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop(proc: subprocess.Popen | None) -> None:
    """Cut off playback immediately — this is what makes barge-in work."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        proc.kill()


def cleanup_speech(path: str | None) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass


def speak_async(text: str, lang: str = "en") -> tuple[subprocess.Popen | None, str | None]:
    """Synthesize local text with gTTS and start playback without blocking.

    Synthesis itself (the gTTS network call) still briefly blocks before
    playback starts — only the playback step is interruptible. Caller must
    call cleanup_speech(path) once done with it, whether stop() cut it off
    early or it finished naturally.
    """
    if not text:
        return None, None
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    gTTS(text=text, lang=lang).save(path)
    return _play_file_async(path), path


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
