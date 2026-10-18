"""Unit tests for voice_loop_demo._timed() (decision 0046) -- the
diagnostic timing helper wrapped around suspected latency sources
(session summarization, the intent-detection LLM fallback, reply
generation, TTS/playback). Asserts only that a log line appears with
the right label, never on exact durations (flaky) or real timing
control.
"""
import asyncio
import logging

from companion_robot.voice_loop_demo import _timed


async def test_timed_logs_one_info_line_with_the_given_label(caplog):
    with caplog.at_level(logging.INFO, logger="companion_robot.voice_loop_demo"):
        async with _timed("reply_generation"):
            await asyncio.sleep(0)

    timing_records = [r for r in caplog.records if r.message.startswith("timing: reply_generation")]
    assert len(timing_records) == 1


async def test_timed_still_logs_when_the_wrapped_call_raises(caplog):
    """Diagnostic logging must not swallow the real exception, and
    must still record the attempt's duration -- a failed call is often
    the most important one to have timing for."""
    with caplog.at_level(logging.INFO, logger="companion_robot.voice_loop_demo"):
        try:
            async with _timed("stt_transcribe"):
                raise ValueError("boom")
        except ValueError:
            pass

    timing_records = [r for r in caplog.records if r.message.startswith("timing: stt_transcribe")]
    assert len(timing_records) == 1
