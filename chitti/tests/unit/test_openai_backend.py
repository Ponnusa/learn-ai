"""Unit tests for companion_robot.voice.openai_backend -- mocked HTTP,
no real API key or network call needed."""
from unittest.mock import MagicMock, patch

import pytest

from companion_robot.voice.openai_backend import OpenAILanguageModelBackend


async def test_reuses_the_same_session_across_multiple_calls(monkeypatch):
    """Decision 0049: a persistent Session (TCP/TLS connection reuse)
    is the whole point of the fix -- a fresh Session per call would
    silently defeat it and bring back the per-call handshake cost."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_response.raise_for_status.return_value = None

    with patch("requests.Session.post", return_value=mock_response):
        backend = OpenAILanguageModelBackend()
        session_before = backend._session
        await backend.generate_reply([{"role": "user", "content": "Hi"}], "system")
        await backend.generate_reply([{"role": "user", "content": "Hi again"}], "system")

    assert backend._session is session_before


async def test_generate_reply_sends_correct_request_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello there!"}}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("requests.Session.post", return_value=mock_response) as mock_post:
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

    with patch("requests.Session.post", return_value=mock_response):
        backend = OpenAILanguageModelBackend(model="gpt-4o")
        _, model = await backend.generate_reply(
            [{"role": "user", "content": "Hi"}], "system"
        )

    assert model == "gpt-4o"


async def test_generate_reply_sends_the_default_max_tokens_cap(monkeypatch):
    """Decision 0047: found live that an uncapped response length was
    a real contributor to reply_generation consistently running far
    slower than this project's own earlier benchmark -- every instance
    now sends a sane default cap unless told otherwise."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_response.raise_for_status.return_value = None

    with patch(
        "requests.Session.post", return_value=mock_response
    ) as mock_post:
        backend = OpenAILanguageModelBackend()
        await backend.generate_reply([{"role": "user", "content": "Hi"}], "system")

    assert mock_post.call_args.kwargs["json"]["max_tokens"] == 300


async def test_generate_reply_uses_custom_max_tokens_and_temperature(monkeypatch):
    """Decision 0047: ConversationService.classify_intent() needs only
    one word back, so it's given a much tighter cap than a full
    conversational reply, plus temperature=0 to keep it terse and
    deterministic."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "STORY"}}]}
    mock_response.raise_for_status.return_value = None

    with patch(
        "requests.Session.post", return_value=mock_response
    ) as mock_post:
        backend = OpenAILanguageModelBackend(max_tokens=10, temperature=0)
        await backend.generate_reply([{"role": "user", "content": "Hi"}], "system")

    assert mock_post.call_args.kwargs["json"]["max_tokens"] == 10
    assert mock_post.call_args.kwargs["json"]["temperature"] == 0


async def test_generate_reply_omits_max_tokens_when_explicitly_none(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_response.raise_for_status.return_value = None

    with patch(
        "requests.Session.post", return_value=mock_response
    ) as mock_post:
        backend = OpenAILanguageModelBackend(max_tokens=None)
        await backend.generate_reply([{"role": "user", "content": "Hi"}], "system")

    assert "max_tokens" not in mock_post.call_args.kwargs["json"]
    assert "temperature" not in mock_post.call_args.kwargs["json"]


async def test_generate_reply_routes_through_azure_when_enabled(monkeypatch):
    """Decision 0110: USE_AZURE_OPENAI switches the URL/auth/model the
    same way config.loader.openai_request() itself is already tested
    to -- this confirms the backend actually calls it rather than its
    own hardcoded OpenAI URL."""
    monkeypatch.setenv("USE_AZURE_OPENAI", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_response.raise_for_status.return_value = None

    with patch("requests.Session.post", return_value=mock_response) as mock_post:
        backend = OpenAILanguageModelBackend(model="gpt-4o-mini")
        reply, model = await backend.generate_reply(
            [{"role": "user", "content": "Hi"}], "system"
        )

    assert reply == "ok"
    assert model == "gpt-4o-mini"  # unmapped -- deployment name matches
    args, kwargs = mock_post.call_args
    assert args[0] == (
        "https://example.openai.azure.com/openai/deployments/gpt-4o-mini/"
        "chat/completions?api-version=2024-12-01-preview"
    )
    assert kwargs["headers"] == {"api-key": "azure-test-key"}
    assert "Authorization" not in kwargs["headers"]
