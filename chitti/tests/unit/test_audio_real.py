"""Unit tests for companion_robot.audio.real.RealAudioTransport --
mocked subprocess and asyncio.sleep, no real aplay/ALSA hardware or
wall-clock waiting needed.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from companion_robot.audio.real import RealAudioTransport


def _mock_proc(alive: bool = True) -> MagicMock:
    proc = MagicMock()
    proc.poll.return_value = None if alive else 1
    proc.stdin = MagicMock()
    return proc


async def test_play_reuses_one_persistent_process_across_calls():
    """The actual bug fix under test: play() must not spawn a fresh
    aplay process (and therefore a fresh ALSA device open) on every
    call -- that's what silently lost the start of short replies on
    real hardware (decision 0016's addendum: "Goodbye! Have a great
    day!" played back as just "day")."""
    proc = _mock_proc()

    with (
        patch("companion_robot.audio.real.subprocess.Popen", return_value=proc) as mock_popen,
        patch("companion_robot.audio.real.asyncio.sleep", new_callable=AsyncMock),
    ):
        transport = RealAudioTransport()
        await transport.play(b"\x00" * 1000)
        await transport.play(b"\x00" * 1000)
        await transport.play(b"\x00" * 1000)

    assert mock_popen.call_count == 1
    assert proc.stdin.write.call_count == 3


async def test_play_respawns_process_if_the_previous_one_died():
    dead_proc = _mock_proc(alive=False)
    fresh_proc = _mock_proc()

    with (
        patch(
            "companion_robot.audio.real.subprocess.Popen", return_value=fresh_proc
        ) as mock_popen,
        patch("companion_robot.audio.real.asyncio.sleep", new_callable=AsyncMock),
    ):
        transport = RealAudioTransport()
        transport._playback_proc = dead_proc  # simulate a process that already exited
        await transport.play(b"\x00" * 1000)

    mock_popen.assert_called_once()
    fresh_proc.stdin.write.assert_called_once()


async def test_stop_playback_terminates_and_clears_the_process():
    proc = _mock_proc()

    with (
        patch("companion_robot.audio.real.subprocess.Popen", return_value=proc),
        patch("companion_robot.audio.real.asyncio.sleep", new_callable=AsyncMock),
    ):
        transport = RealAudioTransport()
        await transport.play(b"\x00" * 1000)
        await transport.stop_playback()

    proc.terminate.assert_called_once()
    assert transport._playback_proc is None


def test_is_muted_always_false_no_physical_switch():
    transport = RealAudioTransport()
    assert transport.is_muted() is False
