"""Cheap OpenAI text completion -- the "cloud" tier of
pixel_ollama_router.py's basic-user routing (general-knowledge
questions too complex for the local model, but not LearnX curriculum
content). Standalone, new file -- same non-interfering pattern as the
other pixel_*.py modules.

Deliberately NOT the Realtime API pixel_openai_voice.py uses -- the
audio side (STT/TTS) is already handled elsewhere in
pixel_ollama_voice.py, so this only ever needs a plain, cheap,
non-streaming text completion.

IMPORTANT COST NOTE: an OpenAI subscription (ChatGPT Plus) is a
completely separate product from API billing -- this calls the API,
billed per token regardless of any consumer subscription you're
paying for. Deliberately uses a cheap/fast model, since this tier is
an overflow valve past the free local model, not meant to replace
LearnX's curriculum handling. The default model name below is NOT yet
confirmed live against a real account -- check
`curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`
and set PIXEL_CLOUD_MODEL if it's not actually available on yours
(same verify-live-don't-guess approach used for the Realtime model
names elsewhere in this project).
"""
import os

import requests

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("PIXEL_CLOUD_MODEL", "gpt-5-mini")

_PERSONA = (
    "You're Pixel, a friendly desk companion robot speaking out loud to "
    "a student. Keep replies short and conversational -- 1 to 3 "
    "sentences, plain spoken language, no markdown, no LaTeX, no "
    "bullet points."
)


def ask(question: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set -- cloud fallback tier unavailable.")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": _PERSONA},
                {"role": "user", "content": question},
            ],
            "max_tokens": 200,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
