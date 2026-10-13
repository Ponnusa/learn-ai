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

Decision 0018: each session ends by summarizing its transcript (via
Claude specifically -- ConversationService's summarizer_llm) into a
DAILY_SUMMARY memory, same spirit as pixel-ai/pixel_memory.py's own
end-of-session summarization. The next session that starts speaks a
casual "welcome back" greeting built from the latest one, so Chitti
can recap what was learned/read last time rather than starting cold
every time it's woken up.

This is explicitly NOT the real continuous-listening architecture the
product eventually wants -- a scoped, honest first real-audio test on
real hardware, not Milestone 2's final design.
"""
import asyncio
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from companion_robot.audio.real import CAPTURE_DEVICE, RealAudioTransport
from companion_robot.conversation.service import ConversationService
from companion_robot.memory.repository import MemoryRepository
from companion_robot.memory.schema import (
    ConsentStatus,
    MemoryCategory,
    MemoryRecord,
    MemorySource,
)
from companion_robot.parent_controls.profiles import ChildProfile, ChildProfileRepository
from companion_robot.parent_controls.stories import StoryRepository
from companion_robot.storage.sqlite import connect
from companion_robot.voice.claude_backend import ClaudeLanguageModelBackend
from companion_robot.voice.openai_backend import OpenAILanguageModelBackend
from companion_robot.voice.stt_openai import OpenAIWhisperBackend
from companion_robot.voice.tts_openai import OpenAITTSBackend

_CAPTURE_PATH = "/tmp/chitti_demo_capture.wav"


def _record_clip(path: str) -> None:
    """Blocking: starts arecord, waits for a second Enter press to
    stop. 16kHz mono 16-bit PCM WAV -- a safe, standard format Whisper
    accepts well. SIGTERM (via terminate()) lets arecord finish
    writing the WAV header cleanly rather than leaving a corrupt file.
    Uses the same CAPTURE_DEVICE override as audio/real.py -- ALSA's
    "default" often doesn't route to the actual USB mic, per pixel-ai's
    own real-hardware experience.
    """
    proc = subprocess.Popen(
        ["arecord", "-D", CAPTURE_DEVICE, "-f", "S16_LE", "-r", "16000", "-c", "1", path],
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
    # Forces English rather than letting Whisper auto-detect -- found
    # live that a short/unclear clip, especially right after a story
    # told in a different language, can get auto-detected wrong
    # entirely and come back as fluent-looking gibberish in a totally
    # unrelated script. Hardcoded for now since English is this
    # project's dev-first language (decision 0003's sequencing); should
    # become a per-profile setting once Finnish is actually in play,
    # not assumed English forever.
    return await stt.transcribe(audio_bytes, language="en")


async def _speak(tts, audio, text: str, speed: float = 1.0) -> None:
    reply_audio = await tts.synthesize(text, speed=speed)
    await audio.play(reply_audio)


def _select_or_create_profile(profiles: ChildProfileRepository) -> ChildProfile:
    """If exactly one child profile exists, use it automatically --
    the common case for a single-child household shouldn't require
    picking from a list of one. With multiple profiles, prompt so the
    right child's memories/speech_speed are actually used, not
    whichever happened to be created first. With none, create one on
    the spot rather than silently defaulting to a fixed "demo-child"
    id the parent never actually set up."""
    existing = profiles.list_all()

    if len(existing) == 1:
        profile = existing[0]
        print(f"Using child profile: {profile.name} (only one set up)")
        return profile

    if existing:
        print("Which child is this?")
        for i, p in enumerate(existing):
            print(f"{i + 1}) {p.name} (age {p.age})")
        print(f"{len(existing) + 1}) Set up a new child")
        choice = input("Pick one: ").strip()
        try:
            idx = int(choice) - 1
        except ValueError:
            idx = -1
        if 0 <= idx < len(existing):
            return existing[idx]
        # Falls through to "create new" for the "new child" option or
        # any unrecognized input, rather than erroring out.

    name = input("Child's name: ").strip() or "Demo Child"
    age_raw = input("Child's age: ").strip()
    age = int(age_raw) if age_raw.isdigit() else 7
    now = datetime.now(timezone.utc)
    profile = ChildProfile(
        id=secrets.token_hex(8), name=name, age=age, created_at=now, updated_at=now
    )
    profiles.create(profile)
    return profile


def _remember_taught_fact(memories: MemoryRepository, child_profile_id: str, text: str) -> None:
    now = datetime.now(timezone.utc)
    memories.create(
        MemoryRecord(
            id=secrets.token_hex(8),
            child_profile_id=child_profile_id,
            category=MemoryCategory.LEARNING_STATE,
            content=f"Taught Chitti: {text}",
            created_at=now,
            updated_at=now,
            source=MemorySource.CHILD,
            consent_or_authorization_status=ConsentStatus.GRANTED,
            retention_policy="demo",
        )
    )


def _remember_story_read(memories: MemoryRepository, child_profile_id: str, title: str) -> None:
    now = datetime.now(timezone.utc)
    memories.create(
        MemoryRecord(
            id=secrets.token_hex(8),
            child_profile_id=child_profile_id,
            category=MemoryCategory.LEARNING_STATE,
            content=f"Read the story: {title}",
            created_at=now,
            updated_at=now,
            source=MemorySource.SYSTEM_INFERRED,
            consent_or_authorization_status=ConsentStatus.GRANTED,
            retention_policy="demo",
        )
    )


async def _summarize_and_remember_session(
    conversation: ConversationService,
    memories: MemoryRepository,
    child_profile_id: str,
    messages: list[dict],
) -> None:
    """Session-end summarization (decision 0018), same spirit as
    pixel-ai/pixel_memory.py's summarize_and_remember() -- one cheap
    call when the session ends, not after every turn. Called from a
    finally block so it still runs on Ctrl-C, not just a clean exit.

    Found live (decision 0021): the Claude call takes a few real
    seconds with no visible feedback, which looks like a second hang
    right after the first Ctrl-C -- pressing Ctrl-C again cancels this
    call mid-flight, before the memory record can be written, and the
    resulting CancelledError propagated all the way up uncaught
    (`except KeyboardInterrupt` doesn't catch it -- different
    exception). Fixed with a visible "Saving..." message so there's no
    reason to interrupt again, plus a catch-all here so a second
    interrupt (or any other failure -- a bad API key, a network
    error) ends the session cleanly instead of crashing during what
    should be a graceful shutdown.
    """
    if not messages:
        return
    print("Saving what we talked about, one moment...")
    try:
        transcript_lines = [f"{m['role']}: {m['content']}" for m in messages]
        summary = await conversation.summarize_session(transcript_lines)
    except asyncio.CancelledError:
        print("(interrupted before saving finished -- this session's summary wasn't saved)")
        return
    except Exception as exc:
        print(f"(couldn't save a summary of this session: {exc})")
        return
    if not summary:
        return
    now = datetime.now(timezone.utc)
    memories.create(
        MemoryRecord(
            id=secrets.token_hex(8),
            child_profile_id=child_profile_id,
            category=MemoryCategory.DAILY_SUMMARY,
            content=summary,
            created_at=now,
            updated_at=now,
            source=MemorySource.SYSTEM_INFERRED,
            consent_or_authorization_status=ConsentStatus.GRANTED,
            retention_policy="demo",
        )
    )
    print("Saved.")


async def _maybe_greet_with_recap(
    conversation: ConversationService, tts, audio, memories: MemoryRepository, profile, speed: float
) -> None:
    """Speaks a "welcome back" greeting built from the most recent
    DAILY_SUMMARY memory for this child, the way a friend would recap
    after being away -- decision 0018. Silently does nothing on the
    very first-ever session, when no prior summary exists yet."""
    summaries = memories.list_for_child(profile.id, category=MemoryCategory.DAILY_SUMMARY)
    if not summaries:
        return
    latest = max(summaries, key=lambda r: r.created_at)
    result = await conversation.welcome_back_greeting(profile.name, latest.content)
    print(f"Chitti: {result.text}")
    await _speak(tts, audio, result.text, speed=speed)


async def _run_teachable_friend(
    conversation, tts, audio, stt, memories, child_profile_id: str, speed: float
) -> None:
    messages: list[dict] = []
    print("\n-- Teachable-Friend mode. Ctrl-C to quit. --")
    try:
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
            await _speak(tts, audio, result.text, speed=speed)
            if not result.blocked:
                _remember_taught_fact(memories, child_profile_id, text)
    finally:
        await _summarize_and_remember_session(conversation, memories, child_profile_id, messages)


async def _run_story_companion(
    conversation, tts, audio, stt, memories, stories, child_profile_id: str, speed: float
) -> None:
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
    await _speak(tts, audio, story.content, speed=speed)
    _remember_story_read(memories, child_profile_id, story.title)

    messages: list[dict] = [{"role": "assistant", "content": story.content}]
    try:
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
            await _speak(tts, audio, result.text, speed=speed)
    finally:
        await _summarize_and_remember_session(conversation, memories, child_profile_id, messages)


async def main() -> None:
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    conn = connect(data_dir / "chitti.db")  # same db file parent_controls/app.py uses

    llm = OpenAILanguageModelBackend()
    # Session summarization/welcome-back greeting specifically use
    # Claude (decision 0018), independent of whichever backend handles
    # live conversation turns -- needs ANTHROPIC_API_KEY in .env too.
    summarizer_llm = ClaudeLanguageModelBackend()
    conversation = ConversationService(llm, summarizer_llm=summarizer_llm)
    stt = OpenAIWhisperBackend()
    tts = OpenAITTSBackend()
    audio = RealAudioTransport()
    memories = MemoryRepository(conn)
    stories = StoryRepository(conn)
    profiles = ChildProfileRepository(conn)

    # Picks the existing profile automatically if there's exactly one
    # (the common single-child case), prompts if there are several,
    # creates one on the spot if there are none -- replaces the old
    # fixed "demo-child" id, which was undiscoverable through the
    # normal Parent Controls profile list and didn't let a household
    # with more than one child pick the right one.
    profile = _select_or_create_profile(profiles)

    # "Hello {name}!" with a casual recap of last time, built from the
    # most recent DAILY_SUMMARY -- decision 0018. Silently skipped on
    # the very first session, before any summary exists yet.
    await _maybe_greet_with_recap(conversation, tts, audio, memories, profile, profile.speech_speed)

    print("Chitti push-to-talk demo.")
    print("1) Teachable-Friend (you teach Chitti something)")
    print("2) Story Companion (Chitti tells a story, answers questions)")
    choice = input("Choose mode (1/2): ").strip()

    try:
        if choice == "2":
            await _run_story_companion(
                conversation, tts, audio, stt, memories, stories, profile.id, profile.speech_speed
            )
        else:
            await _run_teachable_friend(
                conversation, tts, audio, stt, memories, profile.id, profile.speech_speed
            )
    except (KeyboardInterrupt, asyncio.CancelledError):
        # CancelledError shouldn't reach here now that
        # _summarize_and_remember_session() catches it itself
        # (decision 0021), but kept as defense-in-depth against a
        # third interrupt or any other spot it could leak from --
        # better a clean "Bye!" than an unhandled traceback.
        print("\nBye!")


if __name__ == "__main__":
    asyncio.run(main())
