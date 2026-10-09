"""Local speech-to-text server for Pixel's fully-local Ollama pipeline.

Runs on the separate "fast machine" (NOT the Pi) alongside Ollama --
LLaMA 3 / Phi-3 are text-only, with no built-in audio understanding the
way Gemini's generateContent has (see pixel_gemini_voice.py), so
pixel_ollama_voice.py needs a standalone speech-to-text step before
anything reaches the LLM. This is that step: faster-whisper behind a
one-endpoint HTTP server.

Setup (on the fast machine, not the Pi):
    pip install -r requirements-llm-server.txt
    python local_stt_server.py

Exposes one endpoint: POST /transcribe with a WAV file's raw bytes as
the request body -> {"text": "..."}.

No auth, no HTTPS -- same trust model as Ollama's own default HTTP API.
Fine on a trusted home/local network; don't expose this to the public
internet.
"""
import io
import logging
import os

import uvicorn
from fastapi import FastAPI, Request
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

# "base" is a reasonable speed/accuracy default on CPU. Bump to
# "small"/"medium" if the fast machine has a GPU (set
# PIXEL_STT_DEVICE=cuda too) and transcription quality matters more
# than latency.
MODEL_SIZE = os.environ.get("PIXEL_STT_MODEL_SIZE", "base")
DEVICE = os.environ.get("PIXEL_STT_DEVICE", "cpu")
COMPUTE_TYPE = os.environ.get("PIXEL_STT_COMPUTE_TYPE", "int8" if DEVICE == "cpu" else "float16")
HOST = os.environ.get("PIXEL_STT_HOST", "0.0.0.0")
PORT = int(os.environ.get("PIXEL_STT_PORT", "5051"))

app = FastAPI()

logger.info("Loading faster-whisper model %s on %s (%s)...", MODEL_SIZE, DEVICE, COMPUTE_TYPE)
_model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
logger.info("Model loaded, ready to transcribe.")


@app.post("/transcribe")
async def transcribe(request: Request) -> dict:
    wav_bytes = await request.body()
    segments, _ = _model.transcribe(io.BytesIO(wav_bytes), language="en")
    text = " ".join(segment.text.strip() for segment in segments).strip()
    logger.info("transcribed %d bytes -> %r", len(wav_bytes), text)
    return {"text": text}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
