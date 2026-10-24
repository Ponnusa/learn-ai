"""Unit tests for companion_robot.config.loader -- Milestone 1."""
import pytest

from companion_robot.config.loader import (
    load_yaml_config,
    openai_request,
    require_env,
    use_azure_openai,
)


def test_require_env_raises_on_missing(monkeypatch):
    monkeypatch.delenv("CHITTI_TEST_VAR_XYZ", raising=False)
    with pytest.raises(RuntimeError, match="CHITTI_TEST_VAR_XYZ"):
        require_env("CHITTI_TEST_VAR_XYZ")


def test_require_env_returns_value(monkeypatch):
    monkeypatch.setenv("CHITTI_TEST_VAR_XYZ", "hello")
    assert require_env("CHITTI_TEST_VAR_XYZ") == "hello"


def test_load_yaml_config_reads_schema_version(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("schema_version: 1\nfoo: bar\n")
    data = load_yaml_config(config_file)
    assert data["schema_version"] == 1
    assert data["foo"] == "bar"


def test_load_yaml_config_rejects_missing_schema_version(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("foo: bar\n")
    with pytest.raises(RuntimeError, match="schema_version"):
        load_yaml_config(config_file)


# -- decision 0110: Azure OpenAI routing -----------------------------


def test_use_azure_openai_defaults_to_false(monkeypatch):
    monkeypatch.delenv("USE_AZURE_OPENAI", raising=False)
    assert use_azure_openai() is False


@pytest.mark.parametrize("value", ["1", "true", "True", "YES", "yes"])
def test_use_azure_openai_recognizes_truthy_values(monkeypatch, value):
    monkeypatch.setenv("USE_AZURE_OPENAI", value)
    assert use_azure_openai() is True


@pytest.mark.parametrize("value", ["0", "false", "", "no"])
def test_use_azure_openai_recognizes_falsy_values(monkeypatch, value):
    monkeypatch.setenv("USE_AZURE_OPENAI", value)
    assert use_azure_openai() is False


def test_openai_request_targets_direct_openai_by_default(monkeypatch):
    monkeypatch.delenv("USE_AZURE_OPENAI", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    url, headers, model = openai_request("chat/completions", "gpt-4o-mini")

    assert url == "https://api.openai.com/v1/chat/completions"
    assert headers == {"Authorization": "Bearer sk-test"}
    assert model == "gpt-4o-mini"


def test_openai_request_targets_azure_when_enabled(monkeypatch):
    monkeypatch.setenv("USE_AZURE_OPENAI", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    url, headers, model = openai_request("chat/completions", "gpt-4o-mini")

    assert url == (
        "https://example.openai.azure.com/openai/deployments/gpt-4o-mini/"
        "chat/completions?api-version=2024-12-01-preview"
    )
    assert headers == {"api-key": "azure-test-key"}
    assert model == "gpt-4o-mini"  # unmapped -- deployment name matches


@pytest.mark.parametrize(
    ("openai_model", "azure_deployment"),
    [("whisper-1", "whisper"), ("tts-1", "tts")],
)
def test_openai_request_maps_audio_model_names_to_azure_deployments(
    monkeypatch, openai_model, azure_deployment
):
    """Decision 0110: Azure's own deployment names for the audio
    models differ from OpenAI's (confirmed live against a real Azure
    OpenAI resource, same mapping backend/services/ai_router.py's
    own _AZURE_MODEL_MAP already uses)."""
    monkeypatch.setenv("USE_AZURE_OPENAI", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    url, _, model = openai_request("audio/transcriptions", openai_model)

    assert f"/openai/deployments/{azure_deployment}/" in url
    assert model == azure_deployment


def test_openai_request_strips_a_trailing_slash_from_the_endpoint(monkeypatch):
    monkeypatch.setenv("USE_AZURE_OPENAI", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    url, _, _ = openai_request("chat/completions", "gpt-4o")

    assert "//openai" not in url
