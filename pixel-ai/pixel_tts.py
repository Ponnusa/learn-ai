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


def _mpg123_args(path: str) -> list[str]:
    # -b raises mpg123's output buffer; the Pi 1's weak audio path
    # underruns constantly with the default tiny buffer. ALSA's own
    # underrun warnings go straight to stderr regardless of -q, so
    # they're suppressed here too — they're noise, not failures.
    return ["mpg123", "-q", "-b", "2048", path]


def _popen_kwargs() -> dict:
    # stdin=DEVNULL alone isn't enough: mpg123's interactive keyboard
    # controls (pause/seek/quit/bookmark) open /dev/tty directly to grab
    # the controlling terminal, bypassing its own stdin entirely — that's
    # why keystrokes kept getting stolen (and playback could hang/loop)
    # even with stdin redirected. start_new_session=True puts the child
    # in a brand new session with NO controlling terminal at all, so
    # opening /dev/tty fails outright — there's nothing for it to grab,
    # regardless of which mechanism it uses to try.
    return dict(stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def _play_file(path: str) -> None:
    subprocess.run(_mpg123_args(path), check=True, **_popen_kwargs())


def _play_file_async(path: str) -> subprocess.Popen:
    return subprocess.Popen(_mpg123_args(path), **_popen_kwargs())


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
