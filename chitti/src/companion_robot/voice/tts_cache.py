"""Decision 0102: a persistent, disk-based cache for TTS output.

Wraps any TextToSpeechBackend transparently, implementing the same
interface, so none of voice_loop_demo.py's existing _speak() call
sites need to change at all -- just wrap the real backend once in
setup_demo().

Found live: a real hardware session hit a 429 ("Too Many Requests")
from OpenAI's TTS endpoint, and counting the actual log showed why --
many of the spoken lines are exactly the same fixed or deterministically-
templated text every time ("There you go!", "Now it's your turn! Give
it a try.", a phonics breakdown for a specific missed word), each
paying for a fresh, uncached synthesis call regardless. Caching by the
exact (text, voice, model, speed) tuple catches all of that for free,
without curating an explicit list of "known fixed phrases" -- any
text that recurs, for any reason, benefits.
"""
import asyncio
import hashlib
from pathlib import Path

from .interfaces import TextToSpeechBackend


class TTSCache(TextToSpeechBackend):
    """Voice/model are passed in explicitly rather than read off the
    wrapped backend's own attributes, keeping this decoupled from any
    one backend's internals -- a different TextToSpeechBackend
    implementation works here unchanged."""

    def __init__(
        self, backend: TextToSpeechBackend, *, voice: str, model: str, cache_dir: Path,
    ) -> None:
        self._backend = backend
        self._voice = voice
        self._model = model
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _cache_path(self, text: str, speed: float) -> Path:
        raw = f"{text}|{self._voice}|{self._model}|{speed}"
        key = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{key}.pcm"

    async def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        path = self._cache_path(text, speed)
        cached = await asyncio.to_thread(_read_if_exists, path)
        if cached is not None:
            self.hits += 1
            return cached

        self.misses += 1
        audio = await self._backend.synthesize(text, speed=speed)
        # Temp-file-then-rename: an interrupted write (crash, power
        # loss) never leaves a truncated/corrupt cache entry behind
        # for a later run to read back as if it were valid.
        await asyncio.to_thread(_write_atomic, path, audio)
        return audio


def _read_if_exists(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _write_atomic(path: Path, data: bytes) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_bytes(data)
    tmp_path.replace(path)
