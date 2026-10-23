"""Decision 0091: real recorded phonics sounds, one short clip per
grapheme, played directly instead of relying entirely on "'p' like in
'pig'" TTS text (hints.py's own _SOUND_EXAMPLES/blend_breakdown()) --
a proxy that's deliberately not the real sound at all, just a word
that happens to start with it.

Sourced from github.com/minormending/learn-letters (a 44-phoneme UK
chart set, one clip per phoneme) -- used here with the user's own
explicit confirmation they hold the rights to use these recordings.
Converted once (MP3 -> 24kHz mono 16-bit WAV, matching
audio/real.py's RealAudioTransport.play() contract exactly) and
committed as this module's own assets, not fetched at runtime.

Not every grapheme in hints.py's curriculum has a matching clip in
that 44-phoneme source set -- it covers single phonemes, not blends
(qu, ck's covered by reusing plain "c", but "x" is a genuine /ks/
blend with nothing to map), not glued-sound rime chunks (all/ang/ing/
...), and not every long-vowel/diphthong spelling pattern. Deferred
graphemes return None here -- see DEFERRED below for the exact list
and why each one -- so every caller must already have a text fallback
ready (hints.py's existing "like in 'word'" phrasing is exactly that
fallback, unchanged).
"""
import wave
from pathlib import Path

_CLIPS_DIR = Path(__file__).parent / "phonics_sounds"

# Graphemes with no clip yet, and why -- kept as one explicit list
# (not just "whatever file is missing") so it reads as a deliberate,
# reviewed decision, not an oversight to be rediscovered later.
DEFERRED_GRAPHEMES: dict[str, str] = {
    "q": "a /kw/ blend, not a single phoneme the source set has a clip for",
    "x": "a /ks/ blend, not a single phoneme the source set has a clip for",
    "y": "the source clip is the consonant /j/ (\"yes\"); hints.py's "
    "\"y\" is y-as-vowel (\"my\") -- a different sound, not a safe substitute",
    "wh": "not in the source set",
    "ph": "not in the source set",
    "qu": "a /kw/ blend, not a single phoneme",
    "u_e": "the source's closest clip (\"oo\"/moon) is /u:/, not u_e's "
    "/ju:/ (\"cube\") -- close enough to risk teaching it wrong",
    "au": "not in the source set",
    "aw": "not in the source set",
    "all": "a multi-phoneme rime chunk, not a single sound",
    "ang": "a multi-phoneme rime chunk, not a single sound",
    "ing": "a multi-phoneme rime chunk, not a single sound",
    "ong": "a multi-phoneme rime chunk, not a single sound",
    "ung": "a multi-phoneme rime chunk, not a single sound",
    "ank": "a multi-phoneme rime chunk, not a single sound",
    "ink": "a multi-phoneme rime chunk, not a single sound",
    "onk": "a multi-phoneme rime chunk, not a single sound",
    "unk": "a multi-phoneme rime chunk, not a single sound",
}

_cache: dict[str, bytes | None] = {}


def get_clip_bytes(grapheme: str) -> bytes | None:
    """Raw PCM bytes for `grapheme`'s real recorded sound -- pass
    straight to audio.play(). None if this grapheme isn't covered
    (see DEFERRED_GRAPHEMES); callers must have their own text
    fallback ready for that case. Cached after the first read -- these
    are small, fixed files, re-read once per process at most."""
    if grapheme in _cache:
        return _cache[grapheme]
    path = _CLIPS_DIR / f"{grapheme}.wav"
    if not path.exists():
        _cache[grapheme] = None
        return None
    # Reads via the wave module rather than slicing off an assumed
    # header size -- found live, converting these: ffmpeg's header
    # here is 78 bytes, not the canonical 44 (an extra chunk carried
    # over from the source MP3's own metadata), so a fixed offset
    # would have shipped every single clip corrupted by a slice of a
    # non-existent header into real PCM data.
    with wave.open(str(path), "rb") as w:
        pcm = w.readframes(w.getnframes())
    _cache[grapheme] = pcm
    return pcm
