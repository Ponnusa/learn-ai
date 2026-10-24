"""Config validation (spec section 9). Two pieces:

- require_env(): same fail-fast shape as pixel-ai/config.py's
  _require() -- errors clearly on a missing required environment
  variable. Now has real callers: voice/openai_backend.py and
  voice/claude_backend.py (decision 0008).
- load_yaml_config(): loads and minimally validates a YAML config file
  (config/example.yaml, config/development.yaml) -- fails fast if
  schema_version is missing, so a malformed or pre-schema config file
  is caught at startup, not silently misread.

load_dotenv() runs at import time here, same as pixel-ai/config.py --
pixel-ai hit a real bug earlier (pixel_direct_llm.py read os.environ
directly with no .env loading of its own, before it had its own
load_dotenv() call added) because some callers imported it before
anything else had loaded .env. Loading it here, at the one module every
env-reading code path already goes through, avoids repeating that.
"""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


# Decision 0110: lets voice/openai_backend.py, voice/stt_openai.py, and
# voice/tts_openai.py route through Azure OpenAI instead of the direct
# OpenAI API -- same USE_AZURE_OPENAI switch learnai/backend's own
# services/ai_router.py already uses there, applied here to this
# project's raw-requests HTTP calls (no official SDK dependency) rather
# than the openai SDK's AsyncAzureOpenAI client.
_AZURE_DEPLOYMENT_MAP = {
    # Azure deployment names for the audio models differ from OpenAI's
    # own model names (same mapping as the backend's own
    # _AZURE_MODEL_MAP, confirmed live against a real Azure OpenAI
    # resource). gpt-4o/gpt-4o-mini deployment names already match, so
    # no entry needed for those -- an unmapped model passes through
    # unchanged below.
    "whisper-1": "whisper",
    "tts-1": "tts",
}


def use_azure_openai() -> bool:
    return os.environ.get("USE_AZURE_OPENAI", "").strip().lower() in ("1", "true", "yes")


def openai_request(path: str, model: str) -> tuple[str, dict[str, str], str]:
    """Returns (url, headers, effective_model) for calling an
    OpenAI-shaped REST endpoint (`path`, e.g. "chat/completions",
    "audio/transcriptions", "audio/speech") -- either the direct
    OpenAI API or, with USE_AZURE_OPENAI set, the same request
    reshaped for Azure OpenAI: the deployment name in the URL path
    instead of a "model" field, api-version as a query param, and
    api-key auth instead of a bearer token. `effective_model` is the
    Azure deployment name when routed there (the one place a caller
    already put `model` in its own payload keeps working unchanged),
    otherwise `model` itself."""
    if use_azure_openai():
        endpoint = require_env("AZURE_OPENAI_ENDPOINT").rstrip("/")
        api_version = require_env("AZURE_OPENAI_API_VERSION")
        deployment = _AZURE_DEPLOYMENT_MAP.get(model, model)
        url = f"{endpoint}/openai/deployments/{deployment}/{path}?api-version={api_version}"
        headers = {"api-key": require_env("AZURE_OPENAI_API_KEY")}
        return url, headers, deployment
    api_key = require_env("OPENAI_API_KEY")
    return f"https://api.openai.com/v1/{path}", {"Authorization": f"Bearer {api_key}"}, model


def load_yaml_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "schema_version" not in data:
        raise RuntimeError(f"{path}: missing required 'schema_version' field")
    return data
