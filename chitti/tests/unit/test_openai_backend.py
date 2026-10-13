"""Unit tests for companion_robot.voice.openai_backend -- mocked HTTP,
no real API key or network call needed."""
from unittest.mock import MagicMock, patch

import pytest

from companion_robot.voice.openai_backend import OpenAILanguageModelBackend


async def test_generate_reply_sends_correct_request_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello there!"}}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("companion_robot.voice.openai_backend.requests.post", return_value=mock_response) as mock_post:
        backend = OpenAILanguageModelBackend()
        reply, model = await backend.generate_reply(
            [{"role": "user", "content": "Hi"}], "You are a friendly robot."
        )

    assert reply == "Hello there!"
    assert model == "gpt-4o-mini"

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-key-123"
    assert kwargs["json"]["model"] == "gpt-4o-mini"
    assert kwargs["json"]["messages"][0] == {
        "role": "system",
        "content": "You are a friendly robot.",
    }
    assert kwargs["json"]["messages"][1] == {"role": "user", "content": "Hi"}


async def test_generate_reply_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAILanguageModelBackend()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await backend.generate_reply([{"role": "user", "content": "Hi"}], "system")


async def test_generate_reply_uses_custom_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_response.raise_for_status.return_value = None

    with patch("companion_robot.voice.openai_backend.requests.post", return_value=mock_response):
        backend = OpenAILanguageModelBackend(model="gpt-4o")
        _, model = await backend.generate_reply(
            [{"role": "user", "content": "Hi"}], "system"
        )

    assert model == "gpt-4o"
