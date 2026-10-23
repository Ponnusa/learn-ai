"""Unit tests for companion_robot.audio.tones (decision 0084) -- a
deterministic synthesized beep, no hardware needed.
"""
import struct

from companion_robot.audio.real import PLAYBACK_SAMPLE_RATE
from companion_robot.audio.tones import (
    _BEEP_DURATION_SECONDS,
    generate_beep,
)


def test_generate_beep_matches_the_real_transport_playback_format():
    """audio.real.RealAudioTransport.play() expects raw 16-bit signed
    LE mono PCM at PLAYBACK_SAMPLE_RATE, with no header -- the beep
    must be exactly that, not some other rate/width, or it would play
    back distorted or at the wrong pitch/speed on real hardware."""
    beep = generate_beep()
    expected_samples = int(PLAYBACK_SAMPLE_RATE * _BEEP_DURATION_SECONDS)
    assert len(beep) == expected_samples * 2  # 2 bytes per 16-bit sample


def test_generate_beep_is_deterministic():
    assert generate_beep() == generate_beep()


def test_generate_beep_never_clips():
    beep = generate_beep()
    samples = struct.unpack(f"<{len(beep) // 2}h", beep)
    assert max(samples) < 32767
    assert min(samples) > -32768


def test_generate_beep_fades_in_from_silence():
    """No audible click at the very start -- the first sample should
    be at or near zero, not jumping straight to full amplitude."""
    beep = generate_beep()
    first_sample = struct.unpack("<h", beep[:2])[0]
    assert abs(first_sample) < 1000
