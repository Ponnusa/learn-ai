"""Pixel's connection to the LearnX API (learnx-ai.com).

Two real backend flows, verified against backend/routers/chat.py,
videos.py and developer_api.py — not the invented /api/explain the
original spec assumed:

- POST /api/chat/send            -> text explanation (+ vision if image_url set)
- POST /api/public/v1/videos/generate + GET .../videos/{id} -> async video (~60s)

The video endpoints require the public API key (Authorization: Bearer
lx_live_...); chat/send takes a plain user_id/session_id in the body.
"""
import time

import requests

import config

# A plain requests.post()/get() opens a fresh TCP+TLS connection every
# call. On the Pi 1's single 700MHz ARMv6 core (no hardware crypto), that
# handshake is real, repeated overhead — a shared Session keeps the
# connection to the backend warm across calls.
_session = requests.Session()

_TIMEOUT = 15
# chat/send waits synchronously on a GPT-4o completion (up to 2048 tokens)
# plus parallel subject detection — a longer explanation can run well past
# 15s even with nothing wrong on either end.
_CHAT_TIMEOUT = 45
_VIDEO_POLL_INTERVAL = 2
_VIDEO_POLL_TIMEOUT = 90


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {config.LEARNX_API_KEY}"}


def ask(message: str, image_url: str | None = None, conversation_id: str | None = None,
        language: str = config.DEFAULT_LANGUAGE) -> dict:
    """Send a question (optionally with a photo URL) and get a text reply."""
    # user_id only, no session_id: conversations.session_id is a foreign key
    # to a real anonymous_sessions row, and we don't have one — sending a
    # made-up value there breaks the INSERT with a 500.
    payload = {
        "message": message,
        "user_id": config.LEARNX_USER_ID,
        "language": language,
    }
    if image_url:
        payload["image_url"] = image_url
    if conversation_id:
        payload["conversation_id"] = conversation_id

    resp = _session.post(
        f"{config.LEARNX_API_URL}/api/chat/send",
        json=payload,
        timeout=_CHAT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def get_message_audio(message_id: str, language: str = config.DEFAULT_LANGUAGE) -> bytes:
    """Fetch spoken audio for a chat reply — the same endpoint the LearnX
    web app's "read aloud" button uses. The backend runs the message
    through GPT-4o-mini first to strip LaTeX/markdown into natural spoken
    prose (so "$F=ma$" becomes "F equals m a", not literal dollar signs
    and asterisks), then voices it with OpenAI tts-1 and caches the
    result — unlike speaking our own raw text with gTTS, which has no
    idea the message contains markup. No auth header needed.
    """
    resp = _session.get(
        f"{config.LEARNX_API_URL}/api/chat/messages/{message_id}/audio",
        params={"language": language},
        timeout=_CHAT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content


def upload_image(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload an image to the backend and return its public URL."""
    files = {"file": (filename, file_bytes, content_type)}
    data = {"user_id": config.LEARNX_USER_ID}
    resp = _session.post(
        f"{config.LEARNX_API_URL}/api/uploads",
        files=files,
        data=data,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["url"]


def request_video(prompt: str, language: str = config.DEFAULT_LANGUAGE) -> str:
    """Kick off an async Manim video for a short word-problem/prompt. Returns video_id."""
    resp = _session.post(
        f"{config.LEARNX_API_URL}/api/public/v1/videos/generate",
        json={"prompt": prompt, "language": language},
        headers=_auth_headers(),
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["video_id"]


def poll_video(video_id: str, interval: int = _VIDEO_POLL_INTERVAL,
               timeout: int = _VIDEO_POLL_TIMEOUT) -> dict:
    """Poll a video's status until it's done, failed, or the timeout is hit."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = _session.get(
            f"{config.LEARNX_API_URL}/api/public/v1/videos/{video_id}",
            headers=_auth_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") not in ("pending", "processing"):
            return data
        time.sleep(interval)
    raise TimeoutError(f"Video {video_id} did not finish within {timeout}s")
