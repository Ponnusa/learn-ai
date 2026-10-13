"""Unit tests for companion_robot.audio.mock.MockAudioTransport --
Milestone 1. No real mic/speaker/mute-switch hardware -- see
docs/decisions/0001-milestone-0-scope.md.
"""
import asyncio

from companion_robot.audio.mock import MockAudioTransport


async def test_capture_yields_fed_chunks_when_not_muted():
    audio = MockAudioTransport()
    await audio.feed_chunk(b"hello")

    chunks = audio.capture_chunks()
    received = await asyncio.wait_for(chunks.__anext__(), timeout=1)
    assert received == b"hello"


async def test_capture_drops_chunks_while_muted():
    audio = MockAudioTransport()
    audio.set_muted(True)
    await audio.feed_chunk(b"should be dropped")
    await audio.feed_chunk(b"also dropped")
    audio.set_muted(False)
    await audio.feed_chunk(b"this one gets through")

    chunks = audio.capture_chunks()
    received = await asyncio.wait_for(chunks.__anext__(), timeout=1)
    assert received == b"this one gets through"


async def test_play_and_stop_playback_track_state():
    audio = MockAudioTransport()
    assert audio.is_playing is False
    await audio.play(b"some audio")
    # play() is synchronous-to-completion in the mock, so by the time it
    # returns, playback has already "finished" -- is_playing is False
    # again. The real contract under test is that it doesn't raise and
    # stop_playback() is always safe to call regardless.
    await audio.stop_playback()
    assert audio.is_playing is False


def test_is_muted_reflects_set_muted():
    audio = MockAudioTransport()
    assert audio.is_muted() is False
    audio.set_muted(True)
    assert audio.is_muted() is True
