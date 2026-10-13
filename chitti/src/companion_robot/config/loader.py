"""Config validation (spec section 9). Two pieces:

- require_env(): same fail-fast shape as pixel-ai/config.py's
  _require() -- errors clearly on a missing required environment
  variable. No real required variable exists yet (no AI backend chosen
  -- docs/decisions/0004-modular-pipeline-over-realtime.md), but
  Milestone 2+ will need this once one is.
- load_yaml_config(): loads and minimally validates a YAML config file
  (config/example.yaml, config/development.yaml) -- fails fast if
  schema_version is missing, so a malformed or pre-schema config file
  is caught at startup, not silently misread.
"""
import os
from pathlib import Path

import yaml


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
