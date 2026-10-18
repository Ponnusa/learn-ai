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
import contextlib
import difflib
import logging
import os
import secrets
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from companion_robot.audio.real import CAPTURE_DEVICE, PLAYBACK_SAMPLE_RATE, RealAudioTransport
from companion_robot.conversation.service import ConversationResult, ConversationService
from companion_robot.device.interfaces import DeviceState
from companion_robot.device.screen_face import ScreenFaceDeviceController
from companion_robot.diagnostics.logging_setup import configure_logging
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
from companion_robot.intent.router import (
    detect_intent_phrase,
    is_affirmative,
    mentions_activity_keyword,
)
from companion_robot.lullabies.repository import LullabyRepository
from companion_robot.memory.repository import MemoryRepository
from companion_robot.memory.schema import (
    ConsentStatus,
    MemoryCategory,
    MemoryRecord,
    MemorySource,
)
from companion_robot.parent_controls.profiles import ChildProfile, ChildProfileRepository
from companion_robot.parent_controls.reading_exercises import ReadingExerciseRepository
from companion_robot.parent_controls.stories import StoryRepository
from companion_robot.reading.alignment import align, assess, attribute_evidence
from companion_robot.reading.book_generation import BookGenerationError
from companion_robot.reading.decodability import clean_word
from companion_robot.reading.feedback import build_reading_feedback
from companion_robot.reading.hints import build_hint_line, pick_hint_word
from companion_robot.reading.mastery import update_from_evidence
from companion_robot.reading.planner import select_objective
from companion_robot.reading.repository import ReadingRepository
from companion_robot.reading.schema import GeneratedBook
from companion_robot.reading.word_game import (
    blank_vowels,
    incorrect_response,
    is_correct_answer,
    pick_game_words,
    random_closing_line,
    random_correct_response,
    spell_out_blanked,
)
from companion_robot.storage.sqlite import connect
from companion_robot.transcripts.repository import TranscriptRepository
from companion_robot.transcripts.schema import TranscriptRecord
from companion_robot.voice.claude_backend import ClaudeLanguageModelBackend
from companion_robot.voice.openai_backend import OpenAILanguageModelBackend
from companion_robot.voice.stt_openai import OpenAIWhisperBackend
from companion_robot.voice.tts_openai import OpenAITTSBackend

logger = logging.getLogger(__name__)

_CAPTURE_PATH = "/tmp/chitti_demo_capture.wav"


@contextlib.asynccontextmanager
async def _timed(label: str):
    """Decision 0046: diagnostic-only timing around suspected latency
    sources (a mode switch's own session-summary call, the intent-
    detection LLM fallback, reply generation, TTS/playback) -- no
    behavior change, just an INFO log line per wrapped call. Per
    diagnostics/logging_setup.py's own constraint, never logs the
    child's actual text -- only a fixed label and a duration."""
    start = time.monotonic()
    try:
        yield
    finally:
        logger.info("timing: %s took %.2fs", label, time.monotonic() - start)


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
    #
    # Only the transcribe() call itself is timed (decision 0046), not
    # the function above it -- recording time is paced by how long the
    # child takes to talk, not a system latency to diagnose.
    async with _timed("stt_transcribe"):
        return await stt.transcribe(audio_bytes, language="en")


async def _speak(tts, audio, text: str, speed: float = 1.0) -> None:
    # Split (decision 0046): synthesis latency is what feels like lag
    # before Chitti starts responding; playback duration is mostly
    # just the reply being read aloud in real time (RealAudioTransport
    # deliberately waits close to the clip's real duration -- decision
    # 0019), not a processing delay worth conflating with synthesis.
    async with _timed("tts_synthesize"):
        reply_audio = await tts.synthesize(text, speed=speed)
    async with _timed("audio_playback"):
        await audio.play(reply_audio)


# Decision 0050: escalating filler lines spoken while an AI reply is
# still generating, so the wait feels alive instead of silent --
# "camouflaging" the call's latency rather than adding to it, since
# the real work and the filler speech happen concurrently (the real
# call runs as a background task; fillers play in the foreground,
# checking after each one whether the real call has finished yet).
# Fixed, deterministic text -- no LLM call needed just to mask another
# one's latency. Escalates for a longer wait, but never loops/repeats
# once the list is exhausted -- a long tail of silence is preferable
# to an awkward repeated filler.
_THINKING_FILLERS = [
    "Hmm, let me think about that...",
    "Okay, just a little longer...",
    "Almost got it...",
]


async def _speak_while_thinking(task: "asyncio.Task", tts, audio, face, speed: float) -> None:
    for filler in _THINKING_FILLERS:
        if task.done():
            return
        face.set_status_led(DeviceState.SPEAKING)
        await _speak(tts, audio, filler, speed=speed)
        face.set_status_led(DeviceState.PROCESSING)


async def _generate_with_thinking_filler(coro, tts, audio, face, speed: float, label: str):
    """Runs `coro` (the real AI call) in the background while speaking
    escalating filler lines (see _speak_while_thinking) -- decision
    0050. Times the real call's own duration (creation to completion),
    not however long the filler speech happened to take, so decision
    0046's existing timing logs stay accurate regardless of how the
    wait was filled."""
    start = time.monotonic()
    task = asyncio.ensure_future(coro)
    await _speak_while_thinking(task, tts, audio, face, speed)
    result = await task
    logger.info("timing: %s took %.2fs", label, time.monotonic() - start)
    return result


# Decision 0042: reuses the exact menu-choice strings main() already
# dispatches on (see its mode-selection prompt), rather than a parallel
# enum that would just need mapping back to these anyway.
_INTENT_TO_MODE_CHOICE = {"STORY": "2", "SONG": "4", "CHAT": "3", "TEACH": "1", "READ": "5"}


async def _detect_switch_intent(
    text: str, conversation: ConversationService, current_mode: str
) -> tuple[str | None, bool]:
    """Hybrid mode-switch detection (decision 0042). Three tiers, in
    order, each cheaper than the next:
    1. A strict deterministic phrase match (intent/router.py) resolves
       immediately -- free, no LLM call. High confidence: unambiguous
       phrasing.
    2. If the turn doesn't even mention an activity keyword, it's
       definitely not a switch request -- also free, skips the LLM
       entirely. Without this gate, a literal "phrase match, else
       always ask the LLM" design would call the classifier on nearly
       every ordinary conversational turn (anything that isn't an
       exact phrase match), roughly doubling cost/latency for normal
       conversation instead of only paying for genuinely ambiguous
       switch-like phrasing.
    3. Only a turn that mentions an activity keyword but didn't match
       a strict phrase reaches ConversationService.classify_intent()
       (one cheap classification call, not a conversational reply).
       Lower confidence: a judgment call, not a certainty -- decision
       0046 has callers confirm with the child before actually
       switching on this tier, rather than switching silently.

    Returns (mode_code, confident). mode_code is None when nothing
    matched or it resolved to the mode already running, in which case
    confident is always False too.

    Found live (decision 0042 addendum): "I want to teach you
    mathematics" said *while already in Teachable-Friend mode*
    matched the TEACH intent -- correctly -- but with no check against
    the mode already running, that was treated as a "switch" to the
    mode already active, restarting it (re-printing the mode banner,
    discarding the in-progress turn) on every single teaching
    statement, since teaching Chitti something naturally involves
    saying "teach". `current_mode` is the caller's own mode code;
    detecting the mode you're already in is a no-op, not a switch.

    Decision 0048: switching INTO Just Chat ("3") is always treated as
    confident, regardless of which tier detected it -- found live that
    asking "Sounds like you want to just chat -- is that right?" right
    after a child said something emotional ("my friend isn't talking
    to me", right after "I am really sad") read as Chitti not actually
    listening. Unlike Story/Song/Teach, landing in Just Chat by mistake
    costs nothing -- it's the neutral, supportive default mode -- so
    the confirmation step that protects against a jarring *wrong*
    activity switch has no benefit here and a real cost: it delays and
    undercuts the empathetic reply the moment actually calls for.
    """
    phrase_match = detect_intent_phrase(text)
    if phrase_match is not None:
        mode_code = _INTENT_TO_MODE_CHOICE.get(phrase_match)
        confident = True
    elif mentions_activity_keyword(text):
        async with _timed("intent_detection_llm_fallback"):
            label = await conversation.classify_intent(text)
        mode_code = _INTENT_TO_MODE_CHOICE.get(label) if label else None
        confident = False
    else:
        return None, False
    if mode_code is None or mode_code == current_mode:
        return None, False
    if mode_code == "3":
        confident = True
    return mode_code, confident


_CONFIRMATION_PROMPTS = {
    "2": "Sounds like you want to hear a story -- is that right?",
    "4": "Sounds like you want to hear a song -- is that right?",
    "3": "Sounds like you want to just chat -- is that right?",
    "1": "Sounds like you want to teach me something -- is that right?",
    "5": "Sounds like you want to practice reading -- is that right?",
}

_CONFIRMED_ACK = "Great, let's do that!"
_DECLINED_ACK = "Okay, got it."


async def _confirm_switch(mode_code: str, tts, audio, stt, face, speed: float) -> bool:
    """Decision 0046: the LLM-fallback intent tier (see
    _detect_switch_intent's `confident` flag) is a judgment call, not
    a certainty -- for a child-facing device, a silent wrong switch is
    worse than asking once, especially mid-emotional-moment in Just
    Chat (almost happened for real: "my friend isn't talking to me"
    mentions "talk"). Strict phrase matches skip this entirely. Any
    unclear/negative answer defaults to NOT switching, same safer-
    default instinct as _pick_item_by_voice()'s retry.

    Addendum, found live: the child's answer to this question was
    being consumed purely as a yes/no signal and otherwise completely
    discarded -- in one real case it was itself emotionally loaded
    ("yes my friend is not talking to me", repeated for emphasis), and
    getting no acknowledgment at all for it read as Chitti ignoring
    them. A short, fixed, deterministic acknowledgment closes that gap
    cheaply -- not a full LLM-generated reply, which would add another
    round-trip during what's already a slower-than-usual interaction.
    The original trigger text still gets a full real reply right after
    this, in whichever mode ends up running.
    """
    prompt_text = _CONFIRMATION_PROMPTS.get(mode_code, "Is that right?")
    print(f"Chitti: {prompt_text}")
    face.set_status_led(DeviceState.SPEAKING)
    await _speak(tts, audio, prompt_text, speed=speed)
    face.set_status_led(DeviceState.LISTENING)
    answer = await _capture_and_transcribe(stt)
    print(f"You said: {answer}")
    confirmed = is_affirmative(answer)
    ack_text = _CONFIRMED_ACK if confirmed else _DECLINED_ACK
    print(f"Chitti: {ack_text}")
    face.set_status_led(DeviceState.SPEAKING)
    await _speak(tts, audio, ack_text, speed=speed)
    return confirmed


_ORDINAL_WORDS = {
    "first": 0, "1st": 0, "one": 0,
    "second": 1, "2nd": 1, "two": 1,
    "third": 2, "3rd": 2, "three": 2,
}


def _resolve_spoken_choice(spoken: str, items: list) -> object:
    """Resolves a spoken answer to one of `items` (each with a
    `.title`) -- exact title substring match first (the common case:
    the child repeats part of the title), then an ordinal word
    ("first"/"1st"/"one" -> index 0), then a fuzzy title match, then
    defaults to the first item rather than failing outright. Same
    "deterministic, returns a sane default rather than guessing
    wildly" spirit as education/math_check.py."""
    lowered = spoken.lower()
    titles = [item.title for item in items]
    for i, title in enumerate(titles):
        if title.lower() in lowered:
            return items[i]
    for word in lowered.split():
        if word in _ORDINAL_WORDS and _ORDINAL_WORDS[word] < len(items):
            return items[_ORDINAL_WORDS[word]]
    close = difflib.get_close_matches(lowered, [t.lower() for t in titles], n=1, cutoff=0.4)
    if close:
        return items[[t.lower() for t in titles].index(close[0])]
    return items[0]


async def _pick_item_by_voice(
    items: list, label: str, tts, stt, audio, face, speed: float
) -> object:
    """Decision 0042: replaces the old typed numeric picker. If
    there's only one item, returns it with no question asked (today's
    "none yet" early-return in callers is untouched). Otherwise speaks
    the available titles, listens for a spoken answer, and resolves it
    via _resolve_spoken_choice(), with one spoken retry before
    defaulting -- fully voice-driven, consistent with this being a
    push-to-talk voice product rather than a typed-menu one."""
    if len(items) == 1:
        return items[0]
    titles = [item.title for item in items]
    prompt_text = (
        f"I have {len(items)} {label}: {', '.join(titles)}. Which one would you like?"
    )
    print(f"Chitti: {prompt_text}")
    face.set_status_led(DeviceState.SPEAKING)
    await _speak(tts, audio, prompt_text, speed=speed)
    face.set_status_led(DeviceState.LISTENING)
    text = await _capture_and_transcribe(stt)
    print(f"You said: {text}")
    if text.strip():
        return _resolve_spoken_choice(text, items)
    retry_text = "Sorry, I didn't catch that -- let's go with the first one."
    print(f"Chitti: {retry_text}")
    face.set_status_led(DeviceState.SPEAKING)
    await _speak(tts, audio, retry_text, speed=speed)
    return items[0]


def _decode_mp3_to_pcm(path) -> bytes:
    """Decode-only: mpg123 writes raw PCM to its own stdout instead of
    ever opening an ALSA device itself.

    Decision 0041 addendum, found live on the Pi: two earlier versions
    of this function let mpg123 play the file directly through ALSA
    (first via its own default device, then via a forced "-o alsa -a
    PLAYBACK_DEVICE") -- both produced no sound at all, or one audio
    "thud" and silence. Root cause, confirmed via `ps aux` on the Pi:
    RealAudioTransport (audio/real.py) keeps a persistent aplay process
    open on PLAYBACK_DEVICE for the whole session once any TTS reply
    has played -- ALSA hardware devices (plughw) are exclusive, so a
    second process (mpg123) trying to open that same device for
    real-time playback fails, silently, every time. Fix: never let
    mpg123 touch the audio device. It only decodes to a pipe here;
    actual playback goes through the exact same already-open
    RealAudioTransport pipeline every TTS reply already uses (see
    _play_lullaby_file below) -- one ALSA client for the whole
    session, no contention.

    --mono -r PLAYBACK_SAMPLE_RATE matches the fixed format
    RealAudioTransport.play() assumes (16-bit mono PCM at that rate);
    mpg123 resamples/downmixes as needed, so the original file's real
    sample rate/channel count doesn't matter. start_new_session=True
    kept from the original pixel-ai/pixel_tts.py pattern as cheap
    insurance against mpg123 grabbing /dev/tty even in this decode-only
    mode.
    """
    result = subprocess.run(
        ["mpg123", "-q", "-s", "--mono", "-r", str(PLAYBACK_SAMPLE_RATE), str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        check=True,
    )
    return result.stdout


async def _play_lullaby_file(path, audio) -> None:
    pcm = await asyncio.get_event_loop().run_in_executor(None, _decode_mp3_to_pcm, path)
    await audio.play(pcm)


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
        # Decision 0046: this now runs on every mode switch, not just
        # true session end (see run_mode_dispatch_loop) -- timed to
        # confirm/deny it as the dominant latency source.
        async with _timed("session_summary"):
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
    initial_text: str | None = None,
) -> tuple[str | None, str | None]:
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
    # Decision 0042: set when a turn is detected as a request to
    # switch modes -- the loop breaks (still running the finally
    # cleanup below) instead of continuing. Decision 0042 addendum:
    # also carries forward the triggering utterance itself (returned
    # alongside next_mode) so the mode being switched into can reply
    # to it as a real first turn, rather than silently discarding it
    # and making the child repeat themselves -- found live: switching
    # used to go completely silent until the *next* capture, and the
    # utterance that caused the switch never got a reply at all.
    next_mode: str | None = None
    switch_trigger_text: str | None = None
    face.set_expression_mode("learning")  # decision 0044
    print("\n-- Teachable-Friend mode. Ctrl-C to quit. --")
    pending_text = initial_text
    try:
        while True:
            if pending_text is not None:
                text = pending_text
                pending_text = None
            else:
                face.set_status_led(DeviceState.LISTENING)
                text = await _capture_and_transcribe(stt)
                print(f"You said: {text}")
                if not text.strip():
                    print("(nothing heard, try again)")
                    continue
                candidate_mode, confident = await _detect_switch_intent(text, conversation, "1")
                if candidate_mode is not None and (
                    confident
                    or await _confirm_switch(candidate_mode, tts, audio, stt, face, speed)
                ):
                    next_mode = candidate_mode
                    switch_trigger_text = text
                    break
            messages.append({"role": "user", "content": text})
            face.set_status_led(DeviceState.PROCESSING)

            math_check = _resolve_math_check(text, pending_challenge)
            pending_challenge, incorrect_streak = _update_challenge_state(
                math_check, incorrect_streak
            )
            already_tried = incorrect_streak > 1

            result = await _generate_with_thinking_filler(
                conversation.teachable_friend_reply(
                    messages, math_check=math_check, already_tried=already_tried
                ),
                tts, audio, face, speed, "reply_generation",
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
    return next_mode, switch_trigger_text


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
    initial_text: str | None = None,
) -> tuple[str | None, str | None]:
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
    next_mode: str | None = None  # decision 0042, see _run_teachable_friend's comment
    switch_trigger_text: str | None = None
    face.set_expression_mode("chat")  # decision 0044
    print("\n-- Just Chat. Ctrl-C to quit. --")
    pending_text = initial_text
    try:
        while True:
            if pending_text is not None:
                text = pending_text
                pending_text = None
            else:
                face.set_status_led(DeviceState.LISTENING)
                text = await _capture_and_transcribe(stt)
                print(f"You said: {text}")
                if not text.strip():
                    print("(nothing heard, try again)")
                    continue
                candidate_mode, confident = await _detect_switch_intent(text, conversation, "3")
                if candidate_mode is not None and (
                    confident
                    or await _confirm_switch(candidate_mode, tts, audio, stt, face, speed)
                ):
                    next_mode = candidate_mode
                    switch_trigger_text = text
                    break
            messages.append({"role": "user", "content": text})
            face.set_status_led(DeviceState.PROCESSING)

            math_check = _resolve_math_check(text, pending_challenge)
            pending_challenge, incorrect_streak = _update_challenge_state(
                math_check, incorrect_streak
            )
            already_tried = incorrect_streak > 1

            result = await _generate_with_thinking_filler(
                conversation.everyday_companion_reply(
                    messages, math_check=math_check, already_tried=already_tried, child_age=child_age
                ),
                tts, audio, face, speed, "reply_generation",
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
    return next_mode, switch_trigger_text


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
    initial_text: str | None = None,
) -> tuple[str | None, str | None]:
    # initial_text (decision 0042 addendum) is deliberately unused here:
    # unlike Teachable-Friend/Just Chat, Story Companion always starts
    # with a fixed sequence (pick a story, read it, generate its own
    # opening invitation) rather than replying to an arbitrary line, so
    # there's no natural turn to feed a carried-over switch trigger
    # into. Accepted anyway so run_mode_dispatch_loop() can call all
    # three conversational modes the same way.
    all_stories = stories.list_all()
    if not all_stories:
        print("No stories yet -- add one via the Parent Controls web UI first.")
        return None, None
    story = await _pick_item_by_voice(all_stories, "stories", tts, stt, audio, face, speed)

    face.set_expression_mode("story")  # decision 0044
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
    opening = await _generate_with_thinking_filler(
        conversation.story_opening_invitation(story.content, story.title, child_age),
        tts, audio, face, speed, "reply_generation",
    )
    if not opening.blocked:
        print(f"Chitti: {opening.text}")
        messages.append({"role": "assistant", "content": opening.text})
        face.set_status_led(DeviceState.SPEAKING)
        await _speak(tts, audio, opening.text, speed=speed)

    next_mode: str | None = None  # decision 0042, see _run_teachable_friend's comment
    switch_trigger_text: str | None = None
    try:
        while True:
            face.set_status_led(DeviceState.LISTENING)
            text = await _capture_and_transcribe(stt)
            print(f"You said: {text}")
            if not text.strip():
                print("(nothing heard, try again)")
                continue
            candidate_mode, confident = await _detect_switch_intent(text, conversation, "2")
            if candidate_mode is not None and (
                confident or await _confirm_switch(candidate_mode, tts, audio, stt, face, speed)
            ):
                next_mode = candidate_mode
                switch_trigger_text = text
                break
            messages.append({"role": "user", "content": text})
            face.set_status_led(DeviceState.PROCESSING)
            result = await _generate_with_thinking_filler(
                conversation.story_companion_reply(messages, story.content, story.title, child_age),
                tts, audio, face, speed, "reply_generation",
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
    return next_mode, switch_trigger_text


async def _run_lullaby_time(lullabies, face, data_dir: Path, audio, tts, stt, speed: float) -> None:
    """Simple playback, not a conversation (decision 0041): no LLM, no
    transcript/engagement recording -- those all assume conversational
    turns, and there are none here. tts/stt (decision 0042) are only
    used for the voice picker below when there's more than one
    lullaby, not for any conversation."""
    all_lullabies = lullabies.list_all()
    if not all_lullabies:
        print("No lullabies yet -- add one via the Parent Controls web UI first.")
        return
    lullaby = await _pick_item_by_voice(all_lullabies, "lullabies", tts, stt, audio, face, speed)

    face.set_expression_mode("music")  # decision 0044
    print(f"\n-- Lullaby time: {lullaby.title}. Ctrl-C to stop. --")
    # Decision 0050: a short, fixed warm-up line before playback starts
    # instead of jumping straight into the song -- found live that
    # going silent-to-song felt abrupt. Deterministic text, no LLM call
    # needed just to announce what's about to happen.
    face.set_status_led(DeviceState.SPEAKING)
    await _speak(tts, audio, f"I'm going to play {lullaby.title} for you!", speed=speed)
    try:
        await _play_lullaby_file(data_dir / "lullabies" / f"{lullaby.id}.mp3", audio)
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Unlike the conversation modes, this one promises "Ctrl-C to
        # stop" for a single long-running clip rather than a turn
        # boundary -- audio.play() has already handed the full buffer
        # to the persistent aplay process by the time an interrupt
        # lands here, so stopping playback for real needs an explicit
        # stop_playback() call, not just letting the interrupt propagate.
        await audio.stop_playback()
        raise
    finally:
        face.set_status_led(DeviceState.IDLE)


async def _run_comprehension_questions(
    book, conversation, tts, audio, stt, face, speed: float, child_age: int | None = None
) -> None:
    """Decision 0059: 1-2 comprehension questions about the story just
    read, reacted to warmly -- not graded, nothing persisted. Runs for
    every book regardless of source, including a parent-uploaded
    exercise (decision 0052) -- a deliberate precedent change, since
    that path otherwise never touches an LLM at all; both sources look
    identical by this point since both are a GeneratedBook. Always
    offered, not gated behind a yes/no like decision 0057's word game
    -- this is framed as part of finishing the story, not an optional
    side activity. Open-ended "why" questions have no exact expected
    answer, unlike every other grading in this mode, so this reuses
    Story Companion's "ground in the story, react, don't grade"
    pattern (ConversationService.react_to_comprehension_answer())
    instead of a deterministic diff."""
    face.set_status_led(DeviceState.PROCESSING)
    questions = await _generate_with_thinking_filler(
        conversation.generate_comprehension_questions(book.text, age=child_age or 6),
        tts, audio, face, speed, "comprehension_questions",
    )
    if not questions:
        return

    intro = "Let's talk about the story for a moment!"
    print(f"Chitti: {intro}")
    face.set_status_led(DeviceState.SPEAKING)
    await _speak(tts, audio, intro, speed=speed)

    for question in questions:
        print(f"Chitti: {question}")
        face.set_status_led(DeviceState.SPEAKING)
        await _speak(tts, audio, question, speed=speed)

        face.set_status_led(DeviceState.LISTENING)
        answer = await _capture_and_transcribe(stt)
        print(f"You said: {answer}")

        face.set_status_led(DeviceState.PROCESSING)
        reaction = await _generate_with_thinking_filler(
            conversation.react_to_comprehension_answer(
                book.text, question, answer, child_age or 6
            ),
            tts, audio, face, speed, "comprehension_reaction",
        )
        print(f"Chitti: {reaction.text}")
        face.set_status_led(DeviceState.SPEAKING)
        await _speak(tts, audio, reaction.text, speed=speed)


async def _run_word_game(book, tts, audio, stt, face, speed: float) -> None:
    """Decision 0057: a fun, deterministic "missing letters" bonus
    game after a book -- not part of mastery grading (reading/mastery.py
    is never touched here), just encouragement and engagement. Offered,
    not forced: explains itself, checks the child wants to play via
    the same is_affirmative() gate _confirm_switch() uses, and a
    decline/unclear reply skips the whole thing gracefully. Reuses
    decision 0053's set_reading_spotlight() for the blanked-word
    display -- no new rendering needed.
    """
    game_words = pick_game_words(book.words)
    if not game_words:
        return

    intro = (
        "Want to play a quick word game? I'll show you a word from the "
        "story with some letters missing, and you tell me the missing "
        "letters and say the whole word. Ready to play?"
    )
    print(f"Chitti: {intro}")
    face.set_status_led(DeviceState.SPEAKING)
    await _speak(tts, audio, intro, speed=speed)

    face.set_status_led(DeviceState.LISTENING)
    reply = await _capture_and_transcribe(stt)
    print(f"You said: {reply}")
    if not is_affirmative(reply):
        return

    for word in game_words:
        blanked = blank_vowels(word)
        face.set_reading_spotlight(blanked)
        prompt = (
            f"Here's your word: {spell_out_blanked(blanked)}. "
            "What letters are missing, and can you say the whole word?"
        )
        print(f"Chitti: {prompt}")
        face.set_status_led(DeviceState.SPEAKING)
        await _speak(tts, audio, prompt, speed=speed)

        face.set_status_led(DeviceState.LISTENING)
        answer = await _capture_and_transcribe(stt)
        print(f"You said: {answer}")
        face.set_reading_spotlight(None)

        response = (
            random_correct_response()
            if is_correct_answer(word, answer)
            else incorrect_response(word)
        )
        print(f"Chitti: {response}")
        face.set_status_led(DeviceState.SPEAKING)
        await _speak(tts, audio, response, speed=speed)

    closing = random_closing_line()
    print(f"Chitti: {closing}")
    face.set_status_led(DeviceState.SPEAKING)
    await _speak(tts, audio, closing, speed=speed)


async def _run_reading_partner(
    conversation,
    tts,
    audio,
    stt,
    reading_repo: ReadingRepository,
    reading_exercises: ReadingExerciseRepository,
    face,
    child_profile_id: str,
    speed: float,
    child_age: int | None = None,
    child_interest: str = "",
    reading_pace_wpm: float = 45.0,
    reading_font_size: int = 28,
    reading_font_color: str = "white",
    initial_text: str | None = None,
) -> tuple[str | None, str | None]:
    """Decision 0051: phonics-based reading practice -- picks the next
    phonics skill the child hasn't mastered, generates a decodable
    story for it, has the child read it aloud, grades the read via
    deterministic miscue analysis, and updates mastery, looping to the
    next book until the child asks for something else.

    No EngagementRepository/TranscriptRepository use here, same as
    _run_lullaby_time -- reading progress has its own, far more
    meaningful dedicated tracking (reading_profiles/
    reading_grapheme_mastery) than generic turn/word counts would add.

    `initial_text` is accepted for calling-convention uniformity with
    the other modes (decision 0042's carry-forward) but deliberately
    unused -- like _run_story_companion, there's no natural first turn
    to feed it into; the loop always starts by generating the first
    book.

    `child_interest` seeds a brand-new reading profile's own stored
    interest (used to theme every generated book, e.g. "about
    dinosaurs") -- parent-settable from Parent Controls' edit-profile
    page, same place age/speech_speed already live. Once a reading
    profile exists, its own stored value takes over (so an empty
    `child_interest` here never clobbers one already set), which
    `reading_repo.get_or_create()` enforces on its own.

    IMPORTANT, deliberately different from every other mode's turn
    loop: intent-switch detection never runs on the child's read-aloud
    transcript -- that transcript *is* the story's own text, and
    running phrase/keyword detection on arbitrary story content would
    be a real false-positive source. It only runs on the short "want
    another one?" reply between books.

    Decision 0052: if the parent has assigned a reading exercise
    (`reading_exercises.next_pending_for_child()`), that passage is
    used verbatim instead of generating a book -- no decodability
    check, no LLM call -- and marked consumed, so it's read once, not
    every session. Also decision 0052: if the read-aloud surfaces a
    real miscue (substitution/omission), a short graduated hint-and-
    retry exchange runs for that one word before the normal feedback
    -- deliberately post-hoc, not a live mid-sentence interruption,
    since _capture_and_transcribe() is push-to-talk (record until
    Enter, then transcribe once) with no streaming/VAD to notice a
    child pausing mid-read.

    Decision 0053: the book's text is shown as a parent-paced
    (`reading_pace_wpm`), parent-sized/colored (`reading_font_size`/
    `reading_font_color`) scrolling teleprompter -- a pacing aid, not
    reactive to the child's actual speech, same push-to-talk
    limitation as above. `face.set_reading_text()` is called right
    before the read-aloud capture (not before the spoken intro), so
    its internal clock starts close to when the child is actually
    expected to begin reading. During the hint loop, `face.
    set_reading_spotlight(hint_word)` freezes the display on just the
    missed word for the whole hint-and-retry exchange -- the actual
    fix for a confirmed bug where the child had no way to know which
    word a hint was even about.
    """
    face.set_expression_mode("learning")  # decision 0044
    profile = reading_repo.get_or_create(child_profile_id, interest=child_interest)
    print("\n-- Reading Partner. Ctrl-C to quit. --")

    next_mode: str | None = None
    switch_trigger_text: str | None = None
    try:
        while True:
            objective = select_objective(profile, session_index=profile.sessions_completed)
            face.set_status_led(DeviceState.PROCESSING)

            exercise = reading_exercises.next_pending_for_child(child_profile_id)
            exercise_pages = (
                [line.strip() for line in exercise.content.split("\n") if line.strip()]
                if exercise
                else []
            )
            if exercise and exercise_pages:
                book = GeneratedBook(
                    title=exercise.title,
                    pages=exercise_pages,
                    target_grapheme=objective.target_grapheme,
                    objective=objective,
                    sight_words=set(),
                    generation_source="parent_uploaded",
                )
                reading_exercises.mark_consumed(exercise.id)
            else:
                try:
                    book = await _generate_with_thinking_filler(
                        conversation.generate_decodable_book(
                            objective, interest=profile.interest, age=child_age or 6
                        ),
                        tts, audio, face, speed, "reading_book_generation",
                    )
                except BookGenerationError:
                    apology = (
                        "I'm having trouble coming up with a story right now -- "
                        "let's try reading again in a little while."
                    )
                    print(f"Chitti: {apology}")
                    face.set_status_led(DeviceState.SPEAKING)
                    await _speak(tts, audio, apology, speed=speed)
                    break

            print(f"\n-- {book.title} --")
            for page in book.pages:
                print(f"  {page}")
            intro = f'Here\'s your story, "{book.title}"! Give it a try -- read it out loud to me.'
            print(f"Chitti: {intro}")
            face.set_status_led(DeviceState.SPEAKING)
            await _speak(tts, audio, intro, speed=speed)

            # Decision 0053: the teleprompter's clock starts here, as
            # close as practical to when the child is actually
            # expected to start reading -- not before the intro, which
            # would burn several seconds of scroll time while Chitti
            # is still talking.
            face.set_reading_text(
                book.pages,
                wpm=reading_pace_wpm,
                font_size=reading_font_size,
                font_color=reading_font_color,
            )
            face.set_status_led(DeviceState.LISTENING)
            # Real elapsed recording time, not the estimated-duration
            # fallback the original project's typed-transcript CLI path
            # needs -- Chitti's push-to-talk already has a real clock.
            capture_started = time.monotonic()
            spoken = await _capture_and_transcribe(stt)
            duration_seconds = time.monotonic() - capture_started
            print(f"You read: {spoken}")
            face.set_reading_text(None)

            face.set_status_led(DeviceState.PROCESSING)
            assessment = assess(
                book.text, spoken, duration_seconds=duration_seconds, sight_words=book.sight_words
            )

            # Decision 0052: graduated hint + retry for one missed word,
            # before the mastery update so a corrected retry still
            # counts as real evidence rather than being thrown away.
            hint_word = pick_hint_word(assessment)
            hint_resolved = False
            if hint_word is not None:
                # Decision 0053: the actual bug fix -- freezes the
                # display on the missed word for the whole exchange,
                # so the child always knows which word is meant,
                # regardless of hint stage.
                face.set_reading_spotlight(hint_word)
                for stage in range(3):
                    hint_line = build_hint_line(hint_word, stage)
                    print(f"Chitti: {hint_line}")
                    face.set_status_led(DeviceState.SPEAKING)
                    await _speak(tts, audio, hint_line, speed=speed)

                    face.set_status_led(DeviceState.LISTENING)
                    attempt = await _capture_and_transcribe(stt)
                    print(f"You said: {attempt}")

                    retry_evidence = attribute_evidence(
                        align(hint_word, attempt), sight_words=book.sight_words
                    )
                    for grapheme, observations in retry_evidence.items():
                        assessment.grapheme_evidence.setdefault(grapheme, []).extend(observations)

                    if clean_word(attempt) == clean_word(hint_word):
                        hint_resolved = True
                        praise = "There you go!"
                        print(f"Chitti: {praise}")
                        face.set_status_led(DeviceState.SPEAKING)
                        await _speak(tts, audio, praise, speed=speed)
                        break
                # No penalty for still missing it after the third stage
                # (saying the word outright) -- the session just moves on.
                face.set_reading_spotlight(None)

            delta = update_from_evidence(
                profile, assessment.grapheme_evidence, session_index=profile.sessions_completed
            )
            profile.sessions_completed += 1
            reading_repo.save(profile)

            # Decision 0055: only mention the hinted word again if the
            # child never actually got it right -- otherwise cite a
            # standout correctly-read word instead of repeating
            # something already resolved moments ago.
            feedback_text = build_reading_feedback(
                assessment, delta, hint_word=hint_word if not hint_resolved else None
            )
            print(f"Chitti: {feedback_text}")
            face.set_status_led(DeviceState.SPEAKING)
            await _speak(tts, audio, feedback_text, speed=speed)

            # Decision 0059: a couple of comprehension questions about
            # the story, reacted to warmly -- not graded, nothing
            # persisted. Runs before the word game: talk about the
            # story, then play.
            await _run_comprehension_questions(
                book, conversation, tts, audio, stt, face, speed, child_age
            )

            # Decision 0057: a fun, optional bonus game using words
            # from the story -- separate from the grading above.
            await _run_word_game(book, tts, audio, stt, face, speed)

            # Found live: nothing ever told the child Chitti was now
            # waiting on them -- it just silently started listening
            # again after the feedback, with no cue that it was their
            # turn to say whether they wanted another book or
            # something else. This was the original decision 0051
            # plan's own intent ("ask 'want to try another one?'"),
            # never actually spoken in the shipped code.
            next_prompt = "Want to try another one, or would you like to do something else?"
            print(f"Chitti: {next_prompt}")
            face.set_status_led(DeviceState.SPEAKING)
            await _speak(tts, audio, next_prompt, speed=speed)

            face.set_status_led(DeviceState.LISTENING)
            next_text = await _capture_and_transcribe(stt)
            print(f"You said: {next_text}")
            if not next_text.strip():
                continue
            candidate_mode, confident = await _detect_switch_intent(next_text, conversation, "5")
            if candidate_mode is not None and (
                confident or await _confirm_switch(candidate_mode, tts, audio, stt, face, speed)
            ):
                next_mode = candidate_mode
                switch_trigger_text = next_text
                break
    finally:
        face.set_reading_text(None)
        face.set_reading_spotlight(None)
    return next_mode, switch_trigger_text


@dataclass
class DemoContext:
    """Everything a mode-dispatch loop needs, built once by
    setup_demo(). Decision 0043: extracted so both main() (typed
    starting menu) and intent_demo.py (no menu, starts in Just Chat
    and relies on decision 0042's detection for everything after) can
    share the exact same setup and dispatch logic instead of
    duplicating it."""

    conversation: ConversationService
    tts: object
    audio: object
    stt: object
    memories: MemoryRepository
    stories: StoryRepository
    engagement: EngagementRepository
    transcripts: TranscriptRepository
    lullabies: LullabyRepository
    reading: ReadingRepository
    reading_exercises: ReadingExerciseRepository
    face: ScreenFaceDeviceController
    data_dir: Path
    profile: ChildProfile


async def setup_demo() -> DemoContext:
    # Decision 0046: makes the new timing logs (and anything else
    # logged at INFO) actually visible -- previously only app.py called
    # this, so voice_loop_demo.py's own logger.info() calls were
    # silently dropped (no handler configured on the root logger).
    configure_logging()

    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    conn = connect(data_dir / "chitti.db")  # same db file parent_controls/app.py uses

    llm = OpenAILanguageModelBackend()
    # Session summarization/welcome-back greeting specifically use
    # Claude (decision 0018), independent of whichever backend handles
    # live conversation turns -- needs ANTHROPIC_API_KEY in .env too.
    summarizer_llm = ClaudeLanguageModelBackend()
    # Decision 0047: classify_intent() only ever needs to answer with
    # one word (STORY/SONG/CHAT/TEACH/NONE) -- found live it was taking
    # 5.19s on the main conversational backend's much larger token
    # budget. max_tokens=10 is generous for one word; temperature=0
    # keeps it terse and deterministic rather than occasionally
    # elaborating.
    classifier_llm = OpenAILanguageModelBackend(max_tokens=10, temperature=0)
    conversation = ConversationService(
        llm, summarizer_llm=summarizer_llm, classifier_llm=classifier_llm
    )
    stt = OpenAIWhisperBackend()
    tts = OpenAITTSBackend()
    audio = RealAudioTransport()
    memories = MemoryRepository(conn)
    stories = StoryRepository(conn)
    profiles = ChildProfileRepository(conn)
    engagement = EngagementRepository(conn)
    transcripts = TranscriptRepository(conn)
    lullabies = LullabyRepository(conn)
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)

    # Decision 0040: renders listening/thinking/speaking/idle on the
    # HDMI screen. Degrades to "no visible face" on its own (logged,
    # not raised) if pygame isn't installed or no SDL driver works --
    # never allowed to take down a real conversation session.
    #
    # CHITTI_DISABLE_FACE=1 (decision 0046): skips starting the render
    # thread entirely -- an A/B toggle for comparing the timing logs
    # above against the same kind of session with no face rendering at
    # all, to isolate how much (if any) of the observed slowdown is
    # the render thread contending for the Pi's single CPU core versus
    # something else (network conditions, API-side latency). The
    # controller object still exists either way, so every
    # set_status_led()/set_expression_mode() call site is unaffected --
    # they're harmless no-ops while the render thread was never started.
    face = ScreenFaceDeviceController()
    if os.environ.get("CHITTI_DISABLE_FACE") == "1":
        logger.info("CHITTI_DISABLE_FACE=1 -- not starting the face render thread")
    else:
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

    return DemoContext(
        conversation=conversation,
        tts=tts,
        audio=audio,
        stt=stt,
        memories=memories,
        stories=stories,
        engagement=engagement,
        transcripts=transcripts,
        lullabies=lullabies,
        reading=reading,
        reading_exercises=reading_exercises,
        face=face,
        data_dir=data_dir,
        profile=profile,
    )


async def run_mode_dispatch_loop(next_mode: str | None, ctx: DemoContext) -> None:
    """Decision 0042: a mode can detect a child asking to switch
    ("tell me a story" mid-conversation) and return the next mode to
    dispatch instead of just ending -- this loop keeps going for as
    long as that keeps happening, falling through once a mode returns
    None (natural completion, e.g. the lullaby finished, or "no items
    yet"). Ctrl-C is unaffected -- it's an exception, not a return
    value, so it still propagates straight through to the except
    below. Shared by main() and intent_demo.py (decision 0043); only
    how `next_mode` is first obtained differs between them.

    Decision 0042 addendum: `carried_text` is the utterance that
    triggered the switch (if any), passed into whichever mode comes
    next as `initial_text` so it gets a real reply instead of being
    silently discarded -- found live that discarding it forced the
    child to repeat themselves every single time a switch happened.
    """
    carried_text: str | None = None
    try:
        while next_mode is not None:
            if next_mode == "2":
                next_mode, carried_text = await _run_story_companion(
                    ctx.conversation,
                    ctx.tts,
                    ctx.audio,
                    ctx.stt,
                    ctx.memories,
                    ctx.stories,
                    ctx.engagement,
                    ctx.transcripts,
                    ctx.face,
                    ctx.profile.id,
                    ctx.profile.speech_speed,
                    child_age=ctx.profile.age,
                    initial_text=carried_text,
                )
            elif next_mode == "3":
                next_mode, carried_text = await _run_everyday_companion(
                    ctx.conversation,
                    ctx.tts,
                    ctx.audio,
                    ctx.stt,
                    ctx.memories,
                    ctx.engagement,
                    ctx.transcripts,
                    ctx.face,
                    ctx.profile.id,
                    ctx.profile.speech_speed,
                    child_age=ctx.profile.age,
                    initial_text=carried_text,
                )
            elif next_mode == "4":
                # Lullaby time has no listening turn at all, so there's
                # nothing to carry a trigger utterance into -- discard
                # it rather than letting it leak into whatever mode
                # comes after.
                await _run_lullaby_time(
                    ctx.lullabies, ctx.face, ctx.data_dir, ctx.audio, ctx.tts, ctx.stt,
                    ctx.profile.speech_speed,
                )
                next_mode, carried_text = None, None
            elif next_mode == "5":
                next_mode, carried_text = await _run_reading_partner(
                    ctx.conversation,
                    ctx.tts,
                    ctx.audio,
                    ctx.stt,
                    ctx.reading,
                    ctx.reading_exercises,
                    ctx.face,
                    ctx.profile.id,
                    ctx.profile.speech_speed,
                    child_age=ctx.profile.age,
                    child_interest=ctx.profile.interest,
                    reading_pace_wpm=ctx.profile.reading_pace_wpm,
                    reading_font_size=ctx.profile.reading_font_size,
                    reading_font_color=ctx.profile.reading_font_color,
                    initial_text=carried_text,
                )
            else:
                # Matches the original dispatch exactly: anything that
                # isn't "2"/"3"/"4" (including the typed menu's own
                # invalid input, same as before decision 0042) defaults
                # to Teachable-Friend -- never an error message.
                next_mode, carried_text = await _run_teachable_friend(
                    ctx.conversation,
                    ctx.tts,
                    ctx.audio,
                    ctx.stt,
                    ctx.memories,
                    ctx.engagement,
                    ctx.transcripts,
                    ctx.face,
                    ctx.profile.id,
                    ctx.profile.speech_speed,
                    initial_text=carried_text,
                )
    except (KeyboardInterrupt, asyncio.CancelledError):
        # CancelledError shouldn't reach here now that
        # _summarize_and_remember_session() catches it itself
        # (decision 0021), but kept as defense-in-depth against a
        # third interrupt or any other spot it could leak from --
        # better a clean "Bye!" than an unhandled traceback.
        print("\nBye!")
    finally:
        await ctx.face.shutdown()


async def main() -> None:
    ctx = await setup_demo()

    print("Chitti push-to-talk demo.")
    print("1) Teachable-Friend (you teach Chitti something)")
    print("2) Story Companion (Chitti tells a story, answers questions)")
    print("3) Just Chat (talk, play, wonder, or share your day)")
    print("4) Lullaby time (play a song)")
    print("5) Reading Partner (practice reading out loud)")
    next_mode = input("Choose mode (1/2/3/4/5): ").strip()

    await run_mode_dispatch_loop(next_mode, ctx)


if __name__ == "__main__":
    asyncio.run(main())
