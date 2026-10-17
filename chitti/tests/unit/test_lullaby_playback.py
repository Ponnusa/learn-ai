"""Unit tests for voice_loop_demo._decode_mp3_to_pcm/_play_lullaby_file
(decision 0041 addendum) -- mocked subprocess, no real mpg123/audio
hardware needed.

These intentionally do NOT let mpg123 touch an ALSA device at all --
see the addendum in docs/decisions/0041-lullaby-playback.md for why: a
version that did conflicted with RealAudioTransport's own persistent
aplay process (ALSA hardware devices are exclusive), producing total
silence on the real Pi. mpg123 is decode-only here; playback goes
through the same audio.play() pipeline TTS replies already use.
"""
import subprocess
from unittest.mock import MagicMock, patch

from companion_robot.voice_loop_demo import _decode_mp3_to_pcm, _play_lullaby_file


class _FakeAudio:
    def __init__(self) -> None:
        self.played: list[bytes] = []

    async def play(self, audio_bytes: bytes) -> None:
        self.played.append(audio_bytes)


def test_decode_builds_expected_mpg123_argv_and_returns_stdout():
    result = MagicMock(stdout=b"\x00\x01" * 100)

    with patch(
        "companion_robot.voice_loop_demo.subprocess.run", return_value=result
    ) as mock_run:
        pcm = _decode_mp3_to_pcm("/data/lullabies/abc123.mp3")

    args, kwargs = mock_run.call_args
    # -s/--stdout decodes to a pipe instead of opening ALSA directly --
    # the actual fix under test. --mono -r <rate> matches the fixed
    # format RealAudioTransport.play() assumes.
    assert args[0] == [
        "mpg123",
        "-q",
        "-s",
        "--mono",
        "-r",
        "24000",
        "/data/lullabies/abc123.mp3",
    ]
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["check"] is True
    assert kwargs["start_new_session"] is True
    assert pcm == result.stdout


async def test_play_lullaby_file_decodes_then_plays_through_the_shared_pipeline():
    """The actual bug fix: playback must go through audio.play() (the
    same persistent pipeline TTS already uses), never through a second
    mpg123-owned ALSA connection."""
    audio = _FakeAudio()
    decoded_pcm = b"\x00\x01" * 1000

    with patch(
        "companion_robot.voice_loop_demo._decode_mp3_to_pcm", return_value=decoded_pcm
    ):
        await _play_lullaby_file("/data/lullabies/abc123.mp3", audio)

    assert audio.played == [decoded_pcm]
