"""Unit tests for companion_robot.voice.tts_cache.TTSCache -- a
disk-based cache wrapping any TextToSpeechBackend (decision 0102).
"""
from pathlib import Path

from companion_robot.voice.tts_cache import TTSCache


class _FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    async def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        self.calls.append((text, speed))
        return f"audio-for:{text}:{speed}".encode()


async def test_cache_miss_calls_the_backend_and_writes_a_file(tmp_path: Path):
    backend = _FakeBackend()
    cache = TTSCache(backend, voice="alloy", model="tts-1", cache_dir=tmp_path)

    result = await cache.synthesize("Nice reading!", speed=1.0)

    assert result == b"audio-for:Nice reading!:1.0"
    assert backend.calls == [("Nice reading!", 1.0)]
    assert cache.misses == 1
    assert cache.hits == 0
    assert any(tmp_path.iterdir())


async def test_cache_hit_never_calls_the_backend_again(tmp_path: Path):
    backend = _FakeBackend()
    cache = TTSCache(backend, voice="alloy", model="tts-1", cache_dir=tmp_path)

    first = await cache.synthesize("There you go!", speed=1.0)
    second = await cache.synthesize("There you go!", speed=1.0)

    assert first == second
    assert backend.calls == [("There you go!", 1.0)]  # only one real call
    assert cache.misses == 1
    assert cache.hits == 1


async def test_different_speeds_are_different_cache_entries(tmp_path: Path):
    backend = _FakeBackend()
    cache = TTSCache(backend, voice="alloy", model="tts-1", cache_dir=tmp_path)

    await cache.synthesize("Let's keep going!", speed=1.0)
    await cache.synthesize("Let's keep going!", speed=0.75)

    assert backend.calls == [("Let's keep going!", 1.0), ("Let's keep going!", 0.75)]
    assert cache.misses == 2
    assert cache.hits == 0


async def test_different_voice_or_model_are_different_cache_entries(tmp_path: Path):
    backend = _FakeBackend()
    cache_a = TTSCache(backend, voice="alloy", model="tts-1", cache_dir=tmp_path)
    cache_b = TTSCache(backend, voice="echo", model="tts-1", cache_dir=tmp_path)

    await cache_a.synthesize("Good try!", speed=1.0)
    await cache_b.synthesize("Good try!", speed=1.0)

    assert backend.calls == [("Good try!", 1.0), ("Good try!", 1.0)]  # both are misses
    assert cache_a.misses == 1
    assert cache_b.misses == 1


async def test_a_second_cache_instance_reuses_the_same_disk_entries(tmp_path: Path):
    """The whole point of a disk cache over an in-memory one --
    survives a fresh process/instance, not just repeated calls within
    one."""
    backend = _FakeBackend()
    first_instance = TTSCache(backend, voice="alloy", model="tts-1", cache_dir=tmp_path)
    await first_instance.synthesize("Now it's your turn!", speed=1.0)

    second_instance = TTSCache(_FakeBackend(), voice="alloy", model="tts-1", cache_dir=tmp_path)
    result = await second_instance.synthesize("Now it's your turn!", speed=1.0)

    assert result == b"audio-for:Now it's your turn!:1.0"
    assert second_instance.hits == 1
    assert second_instance.misses == 0


async def test_cache_dir_is_created_if_missing(tmp_path: Path):
    cache_dir = tmp_path / "nested" / "tts_cache"
    assert not cache_dir.exists()

    TTSCache(_FakeBackend(), voice="alloy", model="tts-1", cache_dir=cache_dir)

    assert cache_dir.is_dir()
