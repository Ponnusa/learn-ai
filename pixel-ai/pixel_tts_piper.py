"""Local neural text-to-speech for Pixel, via Piper.

Standalone, new file -- same non-interfering pattern as the other
pixel_*.py modules; pixel_tts.py (gTTS, used by every other voice
script) stays untouched.

gTTS calls Google's cloud TTS endpoint over the network for every
utterance -- fine for the cloud-backed voice modes, but inconsistent
with pixel_ollama_voice.py's whole point (fully local, zero API cost,
no internet dependency), and adds a network round-trip's worth of
latency on top of the sentence-streaming pipeline that's already
fighting for every bit of speed there. Piper is a small neural TTS
engine built to run fully offline on exactly this class of hardware
(it's the TTS engine behind Home Assistant's own local voice pipeline
on a Pi) -- runs directly on the Pi itself, not the fast machine,
since it's light enough for that by design and that avoids yet
another network hop on top of the STT/Ollama ones already in the
pipeline.

Same speak_async()/cleanup_speech() interface as pixel_tts.py, so
pixel_ollama_voice.py's _speak_sentence() needed zero changes beyond
importing this module instead.

Setup (on the Pi):
    pip install piper-tts
    mkdir -p ~/piper_voices
    wget -O ~/piper_voices/voice.onnx \
      https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
    wget -O ~/piper_voices/voice.onnx.json \
      https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
    # in .env: PIXEL_PIPER_VOICE=/home/pi/piper_voices/voice.onnx
(browse https://rhasspy.github.io/piper-samples/ for other voices/accents)

NOT yet verified on ARMv6 (the original Pi 1 B+): onnxruntime (Piper's
dependency) only ships prebuilt wheels for armv7l/aarch64, so this
will likely fail to install there -- fine on Pi Zero 2 W / Pi 3 B+ and
newer, the documented production target. Not yet verified live at
all -- no Pi with a Piper voice model downloaded was available while
writing this.
"""
import logging
import os
import subprocess
import tempfile
import wave

from piper import PiperVoice
from piper.voice import SynthesisConfig

logger = logging.getLogger(__name__)

VOICE_MODEL_PATH = os.environ.get("PIXEL_PIPER_VOICE", "")
PLAYBACK_DEVICE = os.environ.get("PIXEL_SPEAKER_DEVICE", "default")

_voice: "PiperVoice | None" = None


def _load_voice() -> "PiperVoice":
    global _voice
    if _voice is None:
        if not VOICE_MODEL_PATH:
            raise RuntimeError(
                "PIXEL_PIPER_VOICE not set -- point it at a downloaded "
                ".onnx Piper voice model (see this file's docstring)."
            )
        logger.info("Loading Piper voice model %s...", VOICE_MODEL_PATH)
        _voice = PiperVoice.load(VOICE_MODEL_PATH)
        logger.info("Piper voice loaded.")
    return _voice


def _synthesize_to_wav(text: str, path: str) -> None:
    voice = _load_voice()
    with wave.open(path, "wb") as wf:
        voice.synthesize_wav(text, wf, syn_config=SynthesisConfig())


def _aplay_args(path: str) -> list[str]:
    return ["aplay", "-D", PLAYBACK_DEVICE, "-q", path]


def _popen_kwargs() -> dict:
    # Same reasoning as pixel_tts.py's _popen_kwargs -- no controlling
    # terminal for the playback process to grab.
    return dict(stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def cleanup_speech(path: str | None) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass


def speak_async(text: str) -> tuple[subprocess.Popen | None, str | None]:
    """Synthesize locally with Piper (no network call) and start
    playback without blocking. Synthesis itself still briefly blocks
    before playback starts -- only the playback step is interruptible.
    Caller must call cleanup_speech(path) once done with it."""
    if not text:
        return None, None
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    _synthesize_to_wav(text, path)
    return subprocess.Popen(_aplay_args(path), **_popen_kwargs()), path


def speak(text: str) -> None:
    """Synthesize and play, blocking until done."""
    if not text:
        return
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        _synthesize_to_wav(text, path)
        subprocess.run(_aplay_args(path), check=True, **_popen_kwargs())
    finally:
        cleanup_speech(path)
