"""Unit tests for companion_robot.reading.word_timing -- parsing and
PCM/WAV wrapping only (decision 0098). The actual Whisper call lives
on OpenAIWhisperBackend; see test_stt_openai_backend.py.
"""
import wave
from io import BytesIO

from companion_robot.reading.word_timing import (
    WordTiming,
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
