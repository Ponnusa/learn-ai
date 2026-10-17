"""Unit tests for voice_loop_demo._play_lullaby_file (decision 0041) --
mocked subprocess and asyncio.sleep, no real mpg123/audio hardware
needed.
"""
import itertools
from unittest.mock import AsyncMock, MagicMock, patch

from companion_robot.voice_loop_demo import _play_lullaby_file


def _mock_proc(alive_for: int = 0) -> MagicMock:
    """poll() returns None (still running) for the first alive_for
    calls, then an exit code for every call after -- simulates a
    process that finishes on its own after a few poll iterations. The
    finally block polls once more after the loop exits, so this must
    keep returning the exit code indefinitely, not just once."""
    proc = MagicMock()
    proc.poll.side_effect = itertools.chain([None] * alive_for, itertools.repeat(0))
    return proc


async def test_builds_expected_mpg123_argv_with_hardware_fixes():
    proc = _mock_proc(alive_for=0)

    with (
        patch("companion_robot.voice_loop_demo.subprocess.Popen", return_value=proc) as mock_popen,
        patch("companion_robot.voice_loop_demo.asyncio.sleep", new_callable=AsyncMock),
        patch("companion_robot.voice_loop_demo.PLAYBACK_DEVICE", "plughw:1,0"),
    ):
        await _play_lullaby_file("/data/lullabies/abc123.mp3")

    args, kwargs = mock_popen.call_args
    # Decision 0041 addendum: must force the ALSA module and the same
    # explicit device audio/real.py's aplay calls use -- mpg123's
    # default ALSA device produced no sound at all on real hardware.
    assert args[0] == [
        "mpg123",
        "-q",
        "-b",
        "2048",
        "-o",
        "alsa",
        "-a",
        "plughw:1,0",
        "/data/lullabies/abc123.mp3",
    ]
    assert kwargs["start_new_session"] is True


async def test_polls_until_the_process_exits_on_its_own():
    proc = _mock_proc(alive_for=3)

    with (
        patch("companion_robot.voice_loop_demo.subprocess.Popen", return_value=proc),
        patch("companion_robot.voice_loop_demo.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await _play_lullaby_file("/data/lullabies/abc123.mp3")

    assert mock_sleep.call_count == 3
    proc.terminate.assert_not_called()


async def test_terminates_the_still_running_process_on_interrupt():
    proc = MagicMock()
    proc.poll.return_value = None  # never exits on its own

    with (
        patch("companion_robot.voice_loop_demo.subprocess.Popen", return_value=proc),
        patch(
            "companion_robot.voice_loop_demo.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=KeyboardInterrupt,
        ),
    ):
        try:
            await _play_lullaby_file("/data/lullabies/abc123.mp3")
        except KeyboardInterrupt:
            pass

    proc.terminate.assert_called_once()
