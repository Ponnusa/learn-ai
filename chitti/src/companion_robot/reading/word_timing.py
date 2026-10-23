"""Word-level timing for Chitti's own TTS playback (decision 0098).

Lets screen_face.py highlight the exact word Chitti is saying during
a modeled read, grounded in the real synthesized audio's own timing
(OpenAI Whisper's word-level timestamps, run against Chitti's own
TTS output) rather than a simulated reading pace. Decision 0088
removed the previous teleprompter specifically because it tracked
elapsed wall-clock time against a guessed words-per-minute pace, not
the real audio, and that desynced badly on real hardware -- grounding
the timing in the actual audio removes that whole failure class
rather than tuning the guess.

Pure parsing/formatting only; the actual Whisper HTTP call lives on
OpenAIWhisperBackend (voice/stt_openai.py), same split every other
reading/ module keeps between its own prompt-building/parsing and
ConversationService holding the real network call.
"""
import io
import wave
from dataclasses import dataclass


@dataclass(frozen=True)
class WordTiming:
    word: str
    start: float
    end: float


def parse_word_timings(response_json: dict) -> list[WordTiming]:
    """Parses OpenAI Whisper's verbose_json word-timestamp format:
    {"words": [{"word": ..., "start": ..., "end": ...}, ...]}.
    Missing/malformed entries are skipped rather than raising -- a
    parse hiccup, or a backend/response that doesn't carry word-level
    timestamps at all, just means the caller skips highlighting
    instead of breaking the read-aloud itself."""
    timings: list[WordTiming] = []
    for entry in response_json.get("words") or []:
        try:
            timings.append(
                WordTiming(
                    word=entry["word"], start=float(entry["start"]), end=float(entry["end"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return timings


def align_timings_to_expected_text(expected_text: str, timings: list[WordTiming]) -> list[WordTiming]:
    """Decision 0098, found live: a real story's sentence read "nap"
    out loud via TTS, but Whisper's own re-transcription of that
    short, clipped word never highlighted -- plausibly Whisper
    mis-hearing or dropping it, a known weakness for short/closed-
    syllable words, especially right at an utterance's edge. We
    already know EXACTLY what text was spoken (we asked the TTS
    backend to say it) -- there's no reason to trust Whisper's own
    transcribed word *text* over that, only its *timing*, which is
    the one thing we can't know in advance. Substitutes each
    timing's word with the corresponding word from `expected_text`,
    matched by position, keeping Whisper's own start/end untouched.
    Only substitutes when the counts match exactly -- if Whisper
    split, merged, or dropped a word, position no longer lines up
    reliably, so this falls back to Whisper's own words unchanged
    rather than guessing a worse mapping."""
    expected_words = expected_text.split()
    if len(expected_words) != len(timings):
        return timings
    return [
        WordTiming(word=expected, start=timing.start, end=timing.end)
        for expected, timing in zip(expected_words, timings)
    ]


def pcm_to_wav_bytes(
    pcm: bytes, *, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2,
) -> bytes:
    """Wraps headerless raw PCM -- OpenAITTSBackend's own output
    format (see its module docstring) -- in a real WAV container.
    Whisper's endpoint needs an actual audio file to parse, not bare
    samples; defaults match PLAYBACK_SAMPLE_RATE/_BYTES_PER_SAMPLE in
    audio/real.py (24kHz, 16-bit, mono)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()
