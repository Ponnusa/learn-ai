"""Push-to-talk demo voice loop (decision 0016): keyboard Enter
start/stop, since this Pi 1 B+ has no physical button and a real
wake-word engine is currently blocked on this exact hardware
(openWakeWord needs an ARMv6 wheel that doesn't exist for either of
its inference backends; Porcupine's ARMv6 support is unconfirmed, not
ruled in or out).

Wires together: real audio capture/playback (audio/real.py), OpenAI
Whisper STT (voice/stt_openai.py), the existing LanguageModelBackend +
ConversationService (Teachable-Friend / Story Companion), OpenAI TTS
(voice/tts_openai.py), and writes a memory record after each
Teachable-Friend exchange (and when a story is read) so the Parent
Controls web UI -- already running against the same
chitti/data/chitti.db -- shows it building live. This is a concrete,
demo-scoped answer to decision 0003's still-open question of whether
Teachable-Friend content ever becomes durable memory: yes, for this
demo, so there's something real for a parent to see.

This is explicitly NOT the real continuous-listening architecture the
product eventually wants -- a scoped, honest first real-audio test on
real hardware, not Milestone 2's final design.
"""
import asyncio
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from companion_robot.audio.real import RealAudioTransport
from companion_robot.conversation.service import ConversationService
from companion_robot.memory.repository import MemoryRepository
from companion_robot.memory.schema import (
    ConsentStatus,
    MemoryCategory,
    MemoryRecord,
    MemorySource,
)
from companion_robot.parent_controls.stories import StoryRepository
from companion_robot.storage.sqlite import connect
from companion_robot.voice.openai_backend import OpenAILanguageModelBackend
from companion_robot.voice.stt_openai import OpenAIWhisperBackend
from companion_robot.voice.tts_openai import OpenAITTSBackend

_CHILD_PROFILE_ID = "demo-child"
_CAPTURE_PATH = "/tmp/chitti_demo_capture.wav"


def _record_clip(path: str) -> None:
    """Blocking: starts arecord, waits for a second Enter press to
    stop. 16kHz mono 16-bit PCM WAV -- a safe, standard format Whisper
    accepts well. SIGTERM (via terminate()) lets arecord finish
    writing the WAV header cleanly rather than leaving a corrupt file.
    """
    proc = subprocess.Popen(
        ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", path],
        stdin=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    input()
    proc.terminate()
    proc.wait(timeout=2)


async def _capture_and_transcribe(stt) -> str:
    print("Press Enter to start talking...")
    input()
    print("Recording -- press Enter to stop.")
    await asyncio.get_event_loop().run_in_executor(None, _record_clip, _CAPTURE_PATH)
    with open(_CAPTURE_PATH, "rb") as f:
        audio_bytes = f.read()
    return await stt.transcribe(audio_bytes)


async def _speak(tts, audio, text: str) -> None:
    reply_audio = await tts.synthesize(text)
    await audio.play(reply_audio)


def _remember_taught_fact(memories: MemoryRepository, text: str) -> None:
    now = datetime.now(timezone.utc)
    memories.create(
        MemoryRecord(
            id=secrets.token_hex(8),
            child_profile_id=_CHILD_PROFILE_ID,
            category=MemoryCategory.LEARNING_STATE,
            content=f"Taught Chitti: {text}",
            created_at=now,
            updated_at=now,
            source=MemorySource.CHILD,
            consent_or_authorization_status=ConsentStatus.GRANTED,
            retention_policy="demo",
        )
    )


def _remember_story_read(memories: MemoryRepository, title: str) -> None:
    now = datetime.now(timezone.utc)
    memories.create(
        MemoryRecord(
            id=secrets.token_hex(8),
            child_profile_id=_CHILD_PROFILE_ID,
            category=MemoryCategory.LEARNING_STATE,
            content=f"Read the story: {title}",
            created_at=now,
            updated_at=now,
            source=MemorySource.SYSTEM_INFERRED,
            consent_or_authorization_status=ConsentStatus.GRANTED,
            retention_policy="demo",
        )
    )


async def _run_teachable_friend(conversation, tts, audio, stt, memories) -> None:
    messages: list[dict] = []
    print("\n-- Teachable-Friend mode. Ctrl-C to quit. --")
    while True:
        text = await _capture_and_transcribe(stt)
        print(f"You said: {text}")
        if not text.strip():
            print("(nothing heard, try again)")
            continue
        messages.append({"role": "user", "content": text})
        result = await conversation.teachable_friend_reply(messages)
        print(f"Chitti: {result.text}")
        messages.append({"role": "assistant", "content": result.text})
        await _speak(tts, audio, result.text)
        if not result.blocked:
            _remember_taught_fact(memories, text)


async def _run_story_companion(conversation, tts, audio, stt, memories, stories) -> None:
    all_stories = stories.list_all()
    if not all_stories:
        print("No stories yet -- add one via the Parent Controls web UI first.")
        return
    for i, s in enumerate(all_stories):
        print(f"{i + 1}) {s.title}")
    choice = input("Pick a story: ").strip()
    try:
        story = all_stories[int(choice) - 1]
    except (ValueError, IndexError):
        print("Not a valid choice.")
        return

    print(f"\n-- Story Companion: {story.title}. Ctrl-C to quit. --")
    print(f"Chitti: {story.content}")
    await _speak(tts, audio, story.content)
    _remember_story_read(memories, story.title)

    messages: list[dict] = [{"role": "assistant", "content": story.content}]
    while True:
        text = await _capture_and_transcribe(stt)
        print(f"You said: {text}")
        if not text.strip():
            print("(nothing heard, try again)")
            continue
        messages.append({"role": "user", "content": text})
        result = await conversation.story_companion_reply(messages, story.content)
        print(f"Chitti: {result.text}")
        messages.append({"role": "assistant", "content": result.text})
        await _speak(tts, audio, result.text)


async def main() -> None:
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    conn = connect(data_dir / "chitti.db")  # same db file parent_controls/app.py uses

    llm = OpenAILanguageModelBackend()
    conversation = ConversationService(llm)
    stt = OpenAIWhisperBackend()
    tts = OpenAITTSBackend()
    audio = RealAudioTransport()
    memories = MemoryRepository(conn)
    stories = StoryRepository(conn)

    print("Chitti push-to-talk demo.")
    print("1) Teachable-Friend (you teach Chitti something)")
    print("2) Story Companion (Chitti tells a story, answers questions)")
    choice = input("Choose mode (1/2): ").strip()

    try:
        if choice == "2":
            await _run_story_companion(conversation, tts, audio, stt, memories, stories)
        else:
            await _run_teachable_friend(conversation, tts, audio, stt, memories)
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    asyncio.run(main())
