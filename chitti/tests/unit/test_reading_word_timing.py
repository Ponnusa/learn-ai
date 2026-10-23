"""Unit tests for companion_robot.reading.word_timing -- parsing and
PCM/WAV wrapping only (decision 0098). The actual Whisper call lives
on OpenAIWhisperBackend; see test_stt_openai_backend.py.
"""
import wave
from io import BytesIO

from companion_robot.reading.word_timing import (
    WordTiming,
    align_timings_to_expected_text,
    parse_word_timings,
    pcm_to_wav_bytes,
)


def test_parse_word_timings_extracts_word_start_end():
    response = {
        "words": [
            {"word": "Dan", "start": 0.0, "end": 0.3},
            {"word": "had", "start": 0.3, "end": 0.6},
        ]
    }
    timings = parse_word_timings(response)
    assert timings == [
        WordTiming(word="Dan", start=0.0, end=0.3),
        WordTiming(word="had", start=0.3, end=0.6),
    ]


def test_parse_word_timings_empty_when_no_words_key():
    assert parse_word_timings({}) == []
    assert parse_word_timings({"text": "Dan had a dog."}) == []


def test_parse_word_timings_skips_malformed_entries_without_raising():
    response = {
        "words": [
            {"word": "Dan", "start": 0.0, "end": 0.3},
            {"word": "had"},  # missing start/end -- skipped, not raised
            {"start": 0.6, "end": 0.9},  # missing word -- skipped
        ]
    }
    timings = parse_word_timings(response)
    assert timings == [WordTiming(word="Dan", start=0.0, end=0.3)]


# -- align_timings_to_expected_text() (decision 0098) ----------------------


def test_align_timings_substitutes_the_known_correct_word_by_position():
    """Found live: Whisper re-transcribing Chitti's own short,
    synthesized "nap" never highlighted at all -- we already know
    the exact text we asked TTS to say, so that's trusted over
    Whisper's own (here apparently wrong) word text; only Whisper's
    timing is kept."""
    timings = [
        WordTiming(word="The", start=0.0, end=0.2),
        WordTiming(word="cat", start=0.2, end=0.4),
        WordTiming(word="can", start=0.4, end=0.6),
        WordTiming(word="gap", start=0.6, end=0.8),  # Whisper mis-heard "nap"
    ]
    aligned = align_timings_to_expected_text("The cat can nap.", timings)

    assert [t.word for t in aligned] == ["The", "cat", "can", "nap."]
    # Timing itself (the one thing we can't know in advance) is kept
    # exactly as Whisper returned it.
    assert aligned[3].start == 0.6 and aligned[3].end == 0.8


def test_align_timings_falls_back_unchanged_when_counts_differ():
    """If Whisper split, merged, or dropped a word, position no
    longer lines up reliably -- falls back to Whisper's own words
    rather than guessing a worse mapping."""
    timings = [WordTiming(word="The", start=0.0, end=0.2), WordTiming(word="cat", start=0.2, end=0.4)]
    aligned = align_timings_to_expected_text("The cat can nap.", timings)

    assert aligned == timings


def test_pcm_to_wav_bytes_produces_a_real_wav_file():
    """OpenAITTSBackend's own output is headerless raw PCM -- Whisper's
    endpoint needs an actual audio file, so this must round-trip
    cleanly through Python's own wave reader."""
    pcm = b"\x00\x01" * 1000
    wav_bytes = pcm_to_wav_bytes(pcm, sample_rate=24000, channels=1, sample_width=2)

    assert wav_bytes[:4] == b"RIFF"
    with wave.open(BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getframerate() == 24000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.readframes(wav_file.getnframes()) == pcm
