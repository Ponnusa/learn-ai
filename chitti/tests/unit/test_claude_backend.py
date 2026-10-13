"""Unit tests for companion_robot.voice.claude_backend -- mocked HTTP,
no real API key or network call needed."""
from unittest.mock import MagicMock, patch

import pytest

from companion_robot.voice.claude_backend import ClaudeLanguageModelBackend


async def test_generate_reply_sends_correct_request_shape(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-456")
    mock_response = MagicMock()
    mock_response.json.return_value = {"content": [{"text": "Hei sinä!"}]}
    mock_response.raise_for_status.return_value = None

    with patch("companion_robot.voice.claude_backend.requests.post", return_value=mock_response) as mock_post:
        backend = ClaudeLanguageModelBackend()
        reply, model = await backend.generate_reply(
            [{"role": "user", "content": "Hei"}], "You are a friendly robot."
        )

    assert reply == "Hei sinä!"
    assert model == "claude-haiku-4-5-20251001"

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["x-api-key"] == "test-key-456"
    assert "Authorization" not in kwargs["headers"]
    assert kwargs["json"]["system"] == "You are a friendly robot."
    assert kwargs["json"]["messages"] == [{"role": "user", "content": "Hei"}]


async def test_generate_reply_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    backend = ClaudeLanguageModelBackend()
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        await backend.generate_reply([{"role": "user", "content": "Hi"}], "system")


async def test_generate_reply_uses_custom_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-456")
    mock_response = MagicMock()
    mock_response.json.return_value = {"content": [{"text": "ok"}]}
    mock_response.raise_for_status.return_value = None

    with patch("companion_robot.voice.claude_backend.requests.post", return_value=mock_response):
        backend = ClaudeLanguageModelBackend(model="claude-sonnet-5-5")
        _, model = await backend.generate_reply(
            [{"role": "user", "content": "Hi"}], "system"
        )

    assert model == "claude-sonnet-5-5"
