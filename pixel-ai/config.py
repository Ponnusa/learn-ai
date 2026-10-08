"""Configuration and environment variables for Pixel AI.

Fails fast on missing required settings instead of calling the backend
unauthenticated with an empty key.
"""
import os
import uuid

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


LEARNX_API_URL = os.environ.get("LEARNX_API_URL", "https://learn-ai-production.up.railway.app").rstrip("/")
LEARNX_API_KEY = _require("LEARNX_API_KEY")
LEARNX_USER_ID = _require("LEARNX_USER_ID")

# One session id per process run — used for /api/chat/send's session_id field.
SESSION_ID = uuid.uuid4().hex

DEFAULT_LANGUAGE = os.environ.get("PIXEL_LANGUAGE", "en")
