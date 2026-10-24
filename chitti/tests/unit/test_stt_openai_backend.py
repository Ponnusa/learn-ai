"""Unit tests for companion_robot.voice.stt_openai -- mocked HTTP, no
real API key or network call needed."""
from unittest.mock import MagicMock, patch

import pytest

from companion_robot.voice.stt_openai import OpenAIWhisperBackend


async def test_reuses_the_same_session_across_multiple_calls(monkeypatch):
    """Decision 0049: a persistent Session (TCP/TLS connection reuse)
    is the whole point of the fix -- a fresh Session per call would
    silently defeat it and bring back the per-call handshake cost."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "Hello Chitti"}
    mock_response.raise_for_status.return_value = None

    with patch("requests.Session.post", return_value=mock_response):
        backend = OpenAIWhisperBackend()
        session_before = backend._session
        await backend.transcribe(b"fake wav bytes")
        await backend.transcribe(b"more fake wav bytes")

    assert backend._session is session_before


async def test_transcribe_sends_correct_request_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "Hello Chitti"}
    mock_response.raise_for_status.return_value = None

    with patch(
        "requests.Session.post", return_value=mock_response
    ) as mock_post:
        backend = OpenAIWhisperBackend()
        text = await backend.transcribe(b"fake wav bytes")

    assert text == "Hello Chitti"
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-key-123"
    assert kwargs["data"]["model"] == "whisper-1"
    assert "language" not in kwargs["data"]  # auto-detect when not given
    assert kwargs["files"]["file"][0] == "audio.wav"
    assert kwargs["files"]["file"][1] == b"fake wav bytes"


async def test_transcribe_passes_through_a_language_hint(monkeypatch):
    """Found live: without this, a short/unclear clip can get its
    language auto-detected wrong entirely, coming back as fluent-
    looking gibberish in an unrelated script instead of a rough
    transcription of what was actually said."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "Hello Chitti"}
    mock_response.raise_for_status.return_value = None

    with patch(
        "requests.Session.post", return_value=mock_response
    ) as mock_post:
        backend = OpenAIWhisperBackend()
        await backend.transcribe(b"fake wav bytes", language="en")

    _, kwargs = mock_post.call_args
    assert kwargs["data"]["language"] == "en"


async def test_transcribe_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAIWhisperBackend()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await backend.transcribe(b"fake wav bytes")


async def test_transcribe_with_word_timestamps_sends_the_right_request_shape(monkeypatch):
    """Decision 0098: unlike transcribe() (plain text, for the child's
    mic input), this requests verbose_json with word-level timestamps
    -- used to recover real, audio-grounded timing from Chitti's own
    synthesized speech for the teleprompter-style highlight."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "words": [{"word": "Hi", "start": 0.0, "end": 0.3}, {"word": "there", "start": 0.3, "end": 0.6}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("requests.Session.post", return_value=mock_response) as mock_post:
        backend = OpenAIWhisperBackend()
        # Raw headerless PCM, same shape OpenAITTSBackend.synthesize()
        # returns -- must arrive at the endpoint wrapped in a real WAV
        # container, not as bare samples.
        timings = await backend.transcribe_with_word_timestamps(b"\x00\x01" * 100)

    assert [t.word for t in timings] == ["Hi", "there"]
    assert timings[0].start == 0.0 and timings[0].end == 0.3
    _, kwargs = mock_post.call_args
    assert kwargs["data"]["response_format"] == "verbose_json"
    assert kwargs["data"]["timestamp_granularities[]"] == "word"
    sent_bytes = kwargs["files"]["file"][1]
    assert sent_bytes[:4] == b"RIFF"  # wrapped in a real WAV container


async def test_transcribe_with_word_timestamps_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAIWhisperBackend()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await backend.transcribe_with_word_timestamps(b"\x00\x01" * 100)


async def test_transcribe_routes_through_azure_when_enabled(monkeypatch):
    """Decision 0110: whisper-1 maps to Azure's own "whisper" deployment
    name (config.loader.openai_request()'s own mapping, confirmed here
    to actually be used by this backend)."""
    monkeypatch.setenv("USE_AZURE_OPENAI", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "Hello Chitti"}
    mock_response.raise_for_status.return_value = None

    with patch("requests.Session.post", return_value=mock_response) as mock_post:
        backend = OpenAIWhisperBackend()
        text = await backend.transcribe(b"fake wav bytes")

    assert text == "Hello Chitti"
    args, kwargs = mock_post.call_args
    assert args[0] == (
        "https://example.openai.azure.com/openai/deployments/whisper/"
        "audio/transcriptions?api-version=2024-12-01-preview"
    )
    assert kwargs["headers"] == {"api-key": "azure-test-key"}
    assert kwargs["data"]["model"] == "whisper"
