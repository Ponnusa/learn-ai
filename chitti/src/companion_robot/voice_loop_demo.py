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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from companion_robot.audio.real import CAPTURE_DEVICE, RealAudioTransport
from companion_robot.conversation.service import ConversationResult, ConversationService
from companion_robot.device.interfaces import DeviceState
from companion_robot.device.screen_face import ScreenFaceDeviceController
from companion_robot.education.math_check import (
    MathCheckResult,
    build_result,
    extract_addition_claim,
    extract_bare_number,
    extract_posed_challenge,
    mentions_number,
)
from companion_robot.engagement.repository import EngagementRepository
from companion_robot.engagement.schema import EngagementMode, EngagementSession
from companion_robot.lullabies.repository import LullabyRepository
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
from companion_robot.transcripts.repository import TranscriptRepository
from companion_robot.transcripts.schema import TranscriptRecord
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


async def _play_lullaby_file(path) -> None:
    """mpg123 pattern adapted from pixel-ai/pixel_tts.py (decision
    0041, same reuse-a-proven-pattern approach decision 0040 used for
    pixel_face.py). Two hard-won fixes carried forward: -b 2048 raises
    mpg123's output buffer, avoiding audio underruns on the Pi 1's weak
    audio path; start_new_session=True puts mpg123 in its own session
    so its keyboard controls can't open /dev/tty and steal keystrokes
    from push-to-talk's own input()-based start/stop -- that matters
    here specifically because nothing else in this project relies on
    keyboard input the way this one does.

    Polls rather than blocking on proc.wait() so Ctrl-C during
    playback (KeyboardInterrupt at the await) reaches the finally
    below and terminates the still-running child -- otherwise, being
    deliberately isolated from the terminal, nothing else would stop
    it.
    """
    proc = subprocess.Popen(
        ["mpg123", "-q", "-b", "2048", str(path)],
        stdin=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        while proc.poll() is None:
            await asyncio.sleep(0.2)
    finally:
        if proc.poll() is None:
            proc.terminate()


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
    story_title: str | None = None,
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

    `story_title` (decision 0022): Story Companion's `messages` only
    ever held the story's body text, never its title, so the
    summarizer had no way to name which story a discussion was about.
    Teachable-Friend has no story, so it's left as None there.
    """
    if not messages:
        return
    print("Saving what we talked about, one moment...")
    try:
        transcript_lines = [f"{m['role']}: {m['content']}" for m in messages]
        if story_title:
            transcript_lines.insert(0, f"(discussing the story: {story_title})")
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


def _record_engagement_session(
    engagement: EngagementRepository,
    child_profile_id: str,
    mode: EngagementMode,
    messages: list[dict],
) -> None:
    """Behavioral telemetry only (decision 0023): how much the child
    spoke this session, not whether what they said was right. No LLM
    involved -- plain counting -- and nothing here is ever spoken back
    to the child as a score."""
    child_turns = [m["content"] for m in messages if m["role"] == "user"]
    if not child_turns:
        return
    engagement.create(
        EngagementSession(
            id=secrets.token_hex(8),
            child_profile_id=child_profile_id,
            mode=mode,
            turn_count=len(child_turns),
            word_count=sum(len(t.split()) for t in child_turns),
            created_at=datetime.now(timezone.utc),
        )
    )


# Decision 0038: how long a transcript stays before it's eligible for
# purge_expired() to remove it -- nothing schedules that purge yet
# (same honest gap MemoryRepository.purge_expired() already has), so
# this is a label on the record today, not an enforced guarantee.
_TRANSCRIPT_RETENTION_DAYS = 90


def _save_transcript(
    transcripts: TranscriptRepository,
    child_profile_id: str,
    mode: EngagementMode,
    messages: list[dict],
) -> None:
    """The full session, for parent transparency (decision 0038) --
    deliberately separate from memory/ (see transcripts/__init__.py
    for why). Reuses the exact same "role: content" line format
    _summarize_and_remember_session() already builds for its own
    summarizer call, rather than inventing a second format."""
    if not messages:
        return
    now = datetime.now(timezone.utc)
    content = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    transcripts.create(
        TranscriptRecord(
            id=secrets.token_hex(8),
            child_profile_id=child_profile_id,
            mode=mode,
            content=content,
            created_at=now,
            consent_or_authorization_status=ConsentStatus.GRANTED,
            retention_policy="demo",
            expires_at=now + timedelta(days=_TRANSCRIPT_RETENTION_DAYS),
        )
    )


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


def _resolve_math_check(
    text: str, pending_challenge: tuple[int, int] | None
) -> MathCheckResult | None:
    """A full self-stated equation ("one plus one is two") always
    wins. Otherwise, if Chitti posed a challenge last turn, a bare
    numeric reply ("4.") is checked against it (decision 0025) -- the
    case decision 0024 didn't cover, since the child never restates
    the operands themselves.

    Found live (decision 0026): a reply that ends in "?" is the child
    asking something back, not answering -- a trailing number in a
    question like "...count two more numbers, what comes next?" isn't
    a claimed sum. Skip the bare-number check in that case (a
    self-stated equation still counts even inside a question, e.g.
    "is 2 plus 2 four?" -- only the pending-challenge path is
    skipped)."""
    math_check = extract_addition_claim(text)
    if math_check is not None or pending_challenge is None:
        return math_check
    if text.rstrip().endswith("?"):
        return None
    claimed_sum = extract_bare_number(text)
    if claimed_sum is None:
        return None
    return build_result(*pending_challenge, claimed_sum)


_MAX_INCORRECT_STREAK = 2  # see _update_challenge_state() below


def _update_challenge_state(
    math_check: MathCheckResult | None, incorrect_streak: int
) -> tuple[tuple[int, int] | None, int]:
    """Decides what to carry into next turn after this one's
    math_check (decision 0027). An incorrect result re-arms
    `pending_challenge` with the SAME problem (instead of clearing it)
    so a flawed follow-up explanation still gets caught, and bumps
    `incorrect_streak` so the prompt note can escalate to the concrete
    walkthrough on a repeat rather than asking to explain again
    indefinitely. Anything else (correct, or no check at all) resets
    both.

    Found live (decision 0028): past `_MAX_INCORRECT_STREAK` tries at
    the same problem, the child tends to have moved on from answering
    the sum to explaining their own counting method instead -- at
    that point the bare-number check starts grabbing numbers that
    mean something else entirely (a step count, not a claimed total),
    producing increasingly irrelevant "still wrong" notes. Past the
    cap, stop re-arming (this turn's own math_check/note is still
    returned and used as normal -- only the *next* round is skipped),
    letting the conversation move on instead of manufacturing more
    confrontational turns."""
    if math_check is None or math_check.correct:
        return None, 0
    new_streak = incorrect_streak + 1
    pending_challenge = (math_check.a, math_check.b) if new_streak <= _MAX_INCORRECT_STREAK else None
    return pending_challenge, new_streak


def _patch_if_still_unresolved(
    result: ConversationResult, math_check: MathCheckResult | None, already_tried: bool
) -> ConversationResult:
    """Decision 0029: a prompt instruction can be ignored by the
    model; this can't. Found live -- on an escalated correction,
    Chitti sometimes hedges without ever actually stating the right
    number ("I can see why you'd say it's 8 that way!"), which isn't
    a clean restated wrong equation extract_addition_claim() would
    catch -- it's just vague agreement. Rather than trying to detect
    every way of hedging (a losing game, and the "universal sentence
    validator" this is deliberately NOT), this only checks the one
    thing that actually matters: does the reply affirm the wrong
    number, or fail to state the right one at all? If so, append a
    short, deterministic correction -- no new LLM call, no retry
    loop, only ever triggered on an already-escalated incorrect
    result."""
    if result.blocked or math_check is None or math_check.correct or not already_tried:
        return result
    restated = extract_addition_claim(result.text)
    says_wrong = restated is not None and restated.claimed_sum == math_check.claimed_sum
    says_correct = mentions_number(result.text, math_check.correct_sum)
    if says_wrong or not says_correct:
        result.text = (
            f"{result.text.rstrip()} Let's count it together -- "
            f"the answer is {math_check.correct_sum}."
        )
    return result


async def _run_teachable_friend(
    conversation,
    tts,
    audio,
    stt,
    memories,
    engagement,
    transcripts,
    face,
    child_profile_id: str,
    speed: float,
) -> None:
    messages: list[dict] = []
    # Tracks an addition challenge Chitti itself posed last turn
    # (decision 0025), so a bare numeric reply next turn ("4.") can
    # still be verified deterministically -- not just a self-stated
    # equation (decision 0024's narrower original case).
    pending_challenge: tuple[int, int] | None = None
    # Found live (decision 0027): after an incorrect claim, the
    # child's follow-up "explain how you got that" turn can itself be
    # a flawed recount that's still wrong -- without re-checking it,
    # Chitti could end up agreeing with the still-wrong number just
    # because it was explained confidently. Counts consecutive
    # incorrect results for the SAME problem so the note can escalate
    # straight to the concrete walkthrough on a repeat, rather than
    # asking to explain again indefinitely.
    incorrect_streak = 0
    print("\n-- Teachable-Friend mode. Ctrl-C to quit. --")
    try:
        while True:
            face.set_status_led(DeviceState.LISTENING)
            text = await _capture_and_transcribe(stt)
            print(f"You said: {text}")
            if not text.strip():
                print("(nothing heard, try again)")
                continue
            messages.append({"role": "user", "content": text})
            face.set_status_led(DeviceState.PROCESSING)

            math_check = _resolve_math_check(text, pending_challenge)
            pending_challenge, incorrect_streak = _update_challenge_state(
                math_check, incorrect_streak
            )
            already_tried = incorrect_streak > 1

            result = await conversation.teachable_friend_reply(
                messages, math_check=math_check, already_tried=already_tried
            )
            result = _patch_if_still_unresolved(result, math_check, already_tried)
            print(f"Chitti: {result.text}")
            messages.append({"role": "assistant", "content": result.text})
            face.set_status_led(DeviceState.SPEAKING)
            await _speak(tts, audio, result.text, speed=speed)
            if not result.blocked:
                _remember_taught_fact(memories, child_profile_id, text)
            if pending_challenge is None:
                pending_challenge = extract_posed_challenge(result.text)
    finally:
        await _summarize_and_remember_session(conversation, memories, child_profile_id, messages)
        _record_engagement_session(
            engagement, child_profile_id, EngagementMode.TEACHABLE_FRIEND, messages
        )
        _save_transcript(transcripts, child_profile_id, EngagementMode.TEACHABLE_FRIEND, messages)


async def _run_everyday_companion(
    conversation,
    tts,
    audio,
    stt,
    memories,
    engagement,
    transcripts,
    face,
    child_profile_id: str,
    speed: float,
    child_age: int | None = None,
) -> None:
    """Decision 0034: the third mode -- everyday chat, simple games,
    spontaneous curiosity, and emotional moments, for when the child
    isn't here to teach Chitti something (mode 1) and no story is
    loaded (mode 2). Reuses the exact same math-check machinery as
    _run_teachable_friend() (all free functions, not tied to that
    loop) so a stray "2 plus 2 is 4" still gets verified here too,
    without duplicating that logic -- TEACHABLE_FRIEND_SYSTEM_PROMPT
    and _run_teachable_friend() itself are untouched by this mode."""
    messages: list[dict] = []
    pending_challenge: tuple[int, int] | None = None
    incorrect_streak = 0
    print("\n-- Just Chat. Ctrl-C to quit. --")
    try:
        while True:
            face.set_status_led(DeviceState.LISTENING)
            text = await _capture_and_transcribe(stt)
            print(f"You said: {text}")
            if not text.strip():
                print("(nothing heard, try again)")
                continue
            messages.append({"role": "user", "content": text})
            face.set_status_led(DeviceState.PROCESSING)

            math_check = _resolve_math_check(text, pending_challenge)
            pending_challenge, incorrect_streak = _update_challenge_state(
                math_check, incorrect_streak
            )
            already_tried = incorrect_streak > 1

            result = await conversation.everyday_companion_reply(
                messages, math_check=math_check, already_tried=already_tried, child_age=child_age
            )
            result = _patch_if_still_unresolved(result, math_check, already_tried)
            print(f"Chitti: {result.text}")
            messages.append({"role": "assistant", "content": result.text})
            face.set_status_led(DeviceState.SPEAKING)
            await _speak(tts, audio, result.text, speed=speed)
            if pending_challenge is None:
                pending_challenge = extract_posed_challenge(result.text)
    finally:
        await _summarize_and_remember_session(conversation, memories, child_profile_id, messages)
        _record_engagement_session(
            engagement, child_profile_id, EngagementMode.EVERYDAY_COMPANION, messages
        )
        _save_transcript(transcripts, child_profile_id, EngagementMode.EVERYDAY_COMPANION, messages)


async def _run_story_companion(
    conversation,
    tts,
    audio,
    stt,
    memories,
    stories,
    engagement,
    transcripts,
    face,
    child_profile_id: str,
    speed: float,
    child_age: int | None = None,
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
    face.set_status_led(DeviceState.SPEAKING)
    await _speak(tts, audio, story.content, speed=speed)
    _remember_story_read(memories, child_profile_id, story.title)

    messages: list[dict] = [{"role": "assistant", "content": story.content}]

    # Decision 0030: found live -- Chitti used to go completely silent
    # here, waiting for the child to speak first. One generated
    # opening observation/question instead, so the conversation
    # actually starts.
    face.set_status_led(DeviceState.PROCESSING)
    opening = await conversation.story_opening_invitation(story.content, story.title, child_age)
    if not opening.blocked:
        print(f"Chitti: {opening.text}")
        messages.append({"role": "assistant", "content": opening.text})
        face.set_status_led(DeviceState.SPEAKING)
        await _speak(tts, audio, opening.text, speed=speed)

    try:
        while True:
            face.set_status_led(DeviceState.LISTENING)
            text = await _capture_and_transcribe(stt)
            print(f"You said: {text}")
            if not text.strip():
                print("(nothing heard, try again)")
                continue
            messages.append({"role": "user", "content": text})
            face.set_status_led(DeviceState.PROCESSING)
            result = await conversation.story_companion_reply(
                messages, story.content, story.title, child_age
            )
            print(f"Chitti: {result.text}")
            messages.append({"role": "assistant", "content": result.text})
            face.set_status_led(DeviceState.SPEAKING)
            await _speak(tts, audio, result.text, speed=speed)
    finally:
        await _summarize_and_remember_session(
            conversation, memories, child_profile_id, messages, story_title=story.title
        )
        _record_engagement_session(
            engagement, child_profile_id, EngagementMode.STORY_COMPANION, messages
        )
        _save_transcript(transcripts, child_profile_id, EngagementMode.STORY_COMPANION, messages)


async def _run_lullaby_time(lullabies, face, data_dir: Path) -> None:
    """Simple playback, not a conversation (decision 0041): no LLM, no
    STT, no transcript/engagement recording -- those all assume
    conversational turns, and there are none here."""
    all_lullabies = lullabies.list_all()
    if not all_lullabies:
        print("No lullabies yet -- add one via the Parent Controls web UI first.")
        return
    for i, lullaby in enumerate(all_lullabies):
        print(f"{i + 1}) {lullaby.title}")
    choice = input("Pick a lullaby: ").strip()
    try:
        lullaby = all_lullabies[int(choice) - 1]
    except (ValueError, IndexError):
        print("Not a valid choice.")
        return

    print(f"\n-- Lullaby time: {lullaby.title}. Ctrl-C to stop. --")
    face.set_status_led(DeviceState.SPEAKING)
    try:
        await _play_lullaby_file(data_dir / "lullabies" / f"{lullaby.id}.mp3")
    finally:
        face.set_status_led(DeviceState.IDLE)


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
    engagement = EngagementRepository(conn)
    transcripts = TranscriptRepository(conn)
    lullabies = LullabyRepository(conn)

    # Decision 0040: renders listening/thinking/speaking/idle on the
    # HDMI screen. Degrades to "no visible face" on its own (logged,
    # not raised) if pygame isn't installed or no SDL driver works --
    # never allowed to take down a real conversation session.
    face = ScreenFaceDeviceController()
    await face.start()

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
    print("3) Just Chat (talk, play, wonder, or share your day)")
    print("4) Lullaby time (play a song)")
    choice = input("Choose mode (1/2/3/4): ").strip()

    try:
        if choice == "2":
            await _run_story_companion(
                conversation,
                tts,
                audio,
                stt,
                memories,
                stories,
                engagement,
                transcripts,
                face,
                profile.id,
                profile.speech_speed,
                child_age=profile.age,
            )
        elif choice == "3":
            await _run_everyday_companion(
                conversation,
                tts,
                audio,
                stt,
                memories,
                engagement,
                transcripts,
                face,
                profile.id,
                profile.speech_speed,
                child_age=profile.age,
            )
        elif choice == "4":
            await _run_lullaby_time(lullabies, face, data_dir)
        else:
            await _run_teachable_friend(
                conversation,
                tts,
                audio,
                stt,
                memories,
                engagement,
                transcripts,
                face,
                profile.id,
                profile.speech_speed,
            )
    except (KeyboardInterrupt, asyncio.CancelledError):
        # CancelledError shouldn't reach here now that
        # _summarize_and_remember_session() catches it itself
        # (decision 0021), but kept as defense-in-depth against a
        # third interrupt or any other spot it could leak from --
        # better a clean "Bye!" than an unhandled traceback.
        print("\nBye!")
    finally:
        await face.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
