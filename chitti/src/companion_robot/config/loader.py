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


def load_yaml_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "schema_version" not in data:
        raise RuntimeError(f"{path}: missing required 'schema_version' field")
    return data
