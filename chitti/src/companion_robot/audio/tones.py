"""Decision 0084: a short, deterministic beep tone -- no TTS call, no
audio asset to ship, just a synthesized sine wave matching
RealAudioTransport's exact raw-PCM contract (16-bit signed LE, mono,
PLAYBACK_SAMPLE_RATE) so it can go through the same audio.play() every
spoken reply already uses.

Built for the new "I'll read it, now you repeat after the beep" help
step: the earlier design relied on a human pressing Enter to tell the
child when to start talking, which doesn't read as natural
conversation. A short, consistent cue tone stands in for that keypress
-- same idea as a camera shutter sound or a game's "go" chime, a
sound a young child can learn to react to without being told what it
means every time.
"""
import math
import struct

from .real import PLAYBACK_SAMPLE_RATE

_BEEP_FREQUENCY_HZ = 880.0  # A5 -- high enough to stand out, not harsh
_BEEP_DURATION_SECONDS = 0.25
_BEEP_AMPLITUDE = 0.4  # well under full scale -- a cue, not a jolt
_BEEP_FADE_SECONDS = 0.02  # avoids an audible click at start/end


def generate_beep() -> bytes:
    """Raw PCM bytes for one short beep, ready for audio.play()."""
    num_samples = int(PLAYBACK_SAMPLE_RATE * _BEEP_DURATION_SECONDS)
    fade_samples = max(1, int(PLAYBACK_SAMPLE_RATE * _BEEP_FADE_SECONDS))
    samples = []
    for i in range(num_samples):
        amplitude = _BEEP_AMPLITUDE
        if i < fade_samples:
            amplitude *= i / fade_samples
        elif i > num_samples - fade_samples:
            amplitude *= (num_samples - i) / fade_samples
        t = i / PLAYBACK_SAMPLE_RATE
        value = amplitude * math.sin(2 * math.pi * _BEEP_FREQUENCY_HZ * t)
        samples.append(int(value * 32767))
    return struct.pack(f"<{num_samples}h", *samples)
