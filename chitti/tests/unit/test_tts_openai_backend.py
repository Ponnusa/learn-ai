"""Unit tests for companion_robot.voice.tts_openai -- mocked HTTP, no
real API key or network call needed."""
from unittest.mock import MagicMock, patch

import pytest

from companion_robot.voice.tts_openai import OpenAITTSBackend


async def test_reuses_the_same_session_across_multiple_calls(monkeypatch):
    """Decision 0049: a persistent Session (TCP/TLS connection reuse)
    is the whole point of the fix -- a fresh Session per call would
    silently defeat it and bring back the per-call handshake cost."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.content = b"fake raw pcm audio bytes"
    mock_response.raise_for_status.return_value = None

    with patch("requests.Session.post", return_value=mock_response):
        backend = OpenAITTSBackend()
        session_before = backend._session
        await backend.synthesize("Hello there!")
        await backend.synthesize("Hello again!")

    assert backend._session is session_before


async def test_synthesize_sends_correct_request_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.content = b"fake raw pcm audio bytes"
    mock_response.raise_for_status.return_value = None

    with patch(
        "requests.Session.post", return_value=mock_response
    ) as mock_post:
        backend = OpenAITTSBackend()
        audio = await backend.synthesize("Hello there!")

    assert audio == b"fake raw pcm audio bytes"
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-key-123"
    assert kwargs["json"]["model"] == "tts-1"
    assert kwargs["json"]["voice"] == "alloy"
    assert kwargs["json"]["input"] == "Hello there!"
    assert kwargs["json"]["response_format"] == "pcm"
    assert kwargs["json"]["speed"] == 1.0


async def test_synthesize_passes_through_a_custom_speed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.content = b"fake raw pcm audio bytes"
    mock_response.raise_for_status.return_value = None

    with patch(
        "requests.Session.post", return_value=mock_response
    ) as mock_post:
        backend = OpenAITTSBackend()
        await backend.synthesize("Slow down please", speed=0.8)

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["speed"] == 0.8


async def test_synthesize_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAITTSBackend()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await backend.synthesize("Hello there!")
