"""Environment-variable validation, same fail-fast shape as
pixel-ai/config.py's _require() -- errors clearly on a missing required
variable instead of letting a caller proceed unauthenticated or
misconfigured. No module calls this yet; it's here for Milestone 1+ to
use once there's a real required variable (e.g. an AI backend API key).
"""
import os


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value
