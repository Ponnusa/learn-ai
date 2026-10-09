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

Decodes the WAV itself with stdlib `wave` instead of handing raw bytes
to faster-whisper's transcribe() (which would decode it via PyAV
internally) -- real-hardware testing hit a faster-whisper/PyAV version
incompatibility (PyAV >= 14 dropped an argument faster-whisper's
decode_audio() still passes; PyAV < 14 has no prebuilt wheel for a
fresh-enough Python and failed to build from source without MSVC Build
Tools). Since we fully control the sender (pixel_ollama_voice.py always
sends 16kHz mono 16-bit PCM), decoding it ourselves and handing
faster-whisper a plain float32 NumPy array instead sidesteps PyAV
entirely -- no version pinning to maintain, one less heavy dependency.
"""
import io
import logging
import os
import wave

import numpy as np
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


def _wav_to_float32(wav_bytes: bytes) -> np.ndarray:
    """faster-whisper expects a mono float32 array at 16kHz when given
    a NumPy array directly (no resampling happens in that path) --
    pixel_ollama_voice.py always records at exactly that rate, so no
    conversion beyond int16 -> float32 is needed here."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        sample_width = wf.getsampwidth()
        channels = wf.getnchannels()
    if sample_width != 2:
        raise ValueError(f"expected 16-bit PCM, got sample width {sample_width}")
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio


@app.post("/transcribe")
async def transcribe(request: Request) -> dict:
    wav_bytes = await request.body()
    audio = _wav_to_float32(wav_bytes)
    segments, _ = _model.transcribe(audio, language="en")
    text = " ".join(segment.text.strip() for segment in segments).strip()
    logger.info("transcribed %d bytes -> %r", len(wav_bytes), text)
    return {"text": text}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
