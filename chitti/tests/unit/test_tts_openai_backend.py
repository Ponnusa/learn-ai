"""Unit tests for companion_robot.voice.tts_openai -- mocked HTTP, no
real API key or network call needed."""
from unittest.mock import MagicMock, patch

import pytest

from companion_robot.voice.tts_openai import OpenAITTSBackend


async def test_synthesize_sends_correct_request_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.content = b"fake wav audio bytes"
    mock_response.raise_for_status.return_value = None

    with patch(
        "companion_robot.voice.tts_openai.requests.post", return_value=mock_response
    ) as mock_post:
        backend = OpenAITTSBackend()
        audio = await backend.synthesize("Hello there!")

    assert audio == b"fake wav audio bytes"
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-key-123"
    assert kwargs["json"]["model"] == "tts-1"
    assert kwargs["json"]["voice"] == "alloy"
    assert kwargs["json"]["input"] == "Hello there!"
    assert kwargs["json"]["response_format"] == "wav"


async def test_synthesize_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAITTSBackend()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await backend.synthesize("Hello there!")
