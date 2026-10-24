"""Unit tests for voice_loop_demo.py's _capture_and_transcribe() own
error handling (decision 0111) -- a transcription failure must never
crash the whole session. The surrounding real recording/file-I/O
machinery (input(), arecord) is patched out so this only exercises
the error-handling path itself.
"""
import companion_robot.voice_loop_demo as voice_loop_demo
from companion_robot.voice_loop_demo import _capture_and_transcribe


class _FailingSTT:
    async def transcribe(self, audio_bytes, language=None):
        raise RuntimeError("429 Too Many Requests")


class _WorkingSTT:
    def __init__(self, text: str) -> None:
        self._text = text

    async def transcribe(self, audio_bytes, language=None):
        return self._text


def _write_fake_capture_file(path: str) -> None:
    with open(path, "wb") as f:
        f.write(b"fake wav bytes")


async def test_returns_empty_string_on_stt_failure_instead_of_raising(monkeypatch):
    """Decision 0111: found live -- an unhandled STT exception (a
    real 429 from an Azure OpenAI deployment mid-quota) used to
    propagate all the way up and crash the entire session. Every one
    of this function's ~20 callers already treats "" as "nothing
    heard, try again" and loops back to prompt again -- this is what
    lets that existing recovery path cover a transcription failure
    too, for free."""
    monkeypatch.setattr("builtins.input", lambda: None)
    monkeypatch.setattr(voice_loop_demo, "_record_clip", _write_fake_capture_file)

    text = await _capture_and_transcribe(_FailingSTT())

    assert text == ""


async def test_still_returns_the_real_transcript_on_success(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda: None)
    monkeypatch.setattr(voice_loop_demo, "_record_clip", _write_fake_capture_file)

    text = await _capture_and_transcribe(_WorkingSTT("hello chitti"))

    assert text == "hello chitti"
