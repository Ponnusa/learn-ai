"""Unit tests for companion_robot.reading.phonics_audio (decision
0091) -- real recorded phonics-sound clips, not generated audio, so
these check the actual shipped files are valid and in the expected
format, plus the deferred-graphemes bookkeeping.
"""
from companion_robot.reading.phonics_audio import DEFERRED_GRAPHEMES, get_clip_bytes


def test_get_clip_bytes_returns_pcm_for_a_covered_grapheme():
    clip = get_clip_bytes("p")
    assert clip is not None
    assert len(clip) > 0
    # 16-bit samples -- an odd byte count would mean a truncated or
    # malformed read.
    assert len(clip) % 2 == 0


def test_get_clip_bytes_is_cached_and_stable():
    first = get_clip_bytes("a")
    second = get_clip_bytes("a")
    assert first == second


def test_get_clip_bytes_returns_none_for_a_deferred_grapheme():
    assert get_clip_bytes("q") is None
    assert get_clip_bytes("y") is None


def test_get_clip_bytes_returns_none_for_an_unknown_grapheme():
    assert get_clip_bytes("not-a-real-grapheme") is None


def test_every_short_vowels_consonant_and_vowel_is_covered_or_deferred():
    """Every grapheme hints.py's own curriculum can produce either has
    a real clip or is explicitly listed in DEFERRED_GRAPHEMES -- never
    silently missing with no record of why."""
    from companion_robot.reading.hints import _SOUND_EXAMPLES

    for grapheme in _SOUND_EXAMPLES:
        covered = get_clip_bytes(grapheme) is not None
        deferred = grapheme in DEFERRED_GRAPHEMES
        assert covered or deferred, f"{grapheme!r} is neither covered nor deferred"
