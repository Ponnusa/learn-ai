"""Unit tests for companion_robot.voice.stt_openai -- mocked HTTP, no
real API key or network call needed."""
from unittest.mock import MagicMock, patch

import pytest

from companion_robot.voice.stt_openai import OpenAIWhisperBackend


async def test_transcribe_sends_correct_request_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "Hello Chitti"}
    mock_response.raise_for_status.return_value = None

    with patch(
        "companion_robot.voice.stt_openai.requests.post", return_value=mock_response
    ) as mock_post:
        backend = OpenAIWhisperBackend()
        text = await backend.transcribe(b"fake wav bytes")

    assert text == "Hello Chitti"
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-key-123"
    assert kwargs["data"]["model"] == "whisper-1"
    assert kwargs["files"]["file"][0] == "audio.wav"
    assert kwargs["files"]["file"][1] == b"fake wav bytes"


async def test_transcribe_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAIWhisperBackend()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await backend.transcribe(b"fake wav bytes")
