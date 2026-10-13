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


async def test_play_does_not_double_wait_when_the_write_already_blocked_in_realtime():
    """The actual bug under test: a long clip (e.g. a multi-sentence
    story) makes stdin.write() block close to real-time once the OS
    pipe fills up, since aplay only drains it as fast as real playback
    consumes it. A first version then slept for the FULL clip duration
    again on top of that, roughly doubling the wait -- found live when
    a story made the program look hung. This proves the fix: when the
    write itself already took ~the full expected duration, the extra
    sleep should be close to just the grace period, not another full
    duration."""
    proc = _mock_proc()
    # 4 seconds of 24kHz 16-bit mono PCM.
    audio = b"\x00" * (24000 * 2 * 4)
    monotonic_calls = iter([0.0, 4.0])  # write "took" exactly 4 real seconds

    with (
        patch("companion_robot.audio.real.subprocess.Popen", return_value=proc),
        patch("companion_robot.audio.real.time.monotonic", side_effect=lambda: next(monotonic_calls)),
        patch("companion_robot.audio.real.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        transport = RealAudioTransport()
        await transport.play(audio)

    slept_for = mock_sleep.call_args.args[0]
    assert slept_for < 1.0  # just the grace period, not another 4 seconds


async def test_play_waits_close_to_full_duration_when_the_write_returned_instantly():
    """The other half of the same fix: a short clip that fits entirely
    in the OS pipe buffer returns from write() almost immediately, long
    before actual playback has finished -- that case still needs to
    wait close to the full clip duration, not just the grace period."""
    proc = _mock_proc()
    audio = b"\x00" * (24000 * 2 * 2)  # 2 seconds of audio
    monotonic_calls = iter([0.0, 0.01])  # write returned almost instantly

    with (
        patch("companion_robot.audio.real.subprocess.Popen", return_value=proc),
        patch("companion_robot.audio.real.time.monotonic", side_effect=lambda: next(monotonic_calls)),
        patch("companion_robot.audio.real.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        transport = RealAudioTransport()
        await transport.play(audio)

    slept_for = mock_sleep.call_args.args[0]
    assert slept_for > 1.5  # close to the full ~2 second duration, not just the grace period
