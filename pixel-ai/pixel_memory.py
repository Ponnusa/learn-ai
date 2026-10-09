"""Persistent persona + memory for Pixel's casual chat.

Standalone module, new file — imported by pixel_gemini_text.py but
doesn't touch any existing script. Two plain text files instead of a
database, same spirit as OmniBot's persona-file pattern:

- persona/IDENTITY.md — Pixel's own personality. Generic, safe to commit.
- persona/MEMORY.md   — facts about the specific student. Personal data,
  gitignored, never committed. Created on first write if missing.

Without this, client.chats.create()'s history (what pixel_gemini_text.py
already has) only lasts for one running process — restart the script and
Pixel remembers nothing. This makes a few durable facts survive restarts
without needing any real backend or database.
"""
import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_PERSONA_DIR = os.path.join(os.path.dirname(__file__), "persona")
_IDENTITY_PATH = os.path.join(_PERSONA_DIR, "IDENTITY.md")
_MEMORY_PATH = os.path.join(_PERSONA_DIR, "MEMORY.md")
# Raw per-session transcripts, saved before summarization is even
# attempted -- a safety net so a crashed/failed summarization call
# doesn't lose the conversation outright (it used to live only in an
# in-memory list that died with the process). Gitignored, same
# sensitivity as MEMORY.md.
_TRANSCRIPT_DIR = os.path.join(_PERSONA_DIR, "transcripts")
_CURRENT_HEADER = "## Current"
_HISTORY_HEADER = "## History"
# Pixel's current name, chosen by whoever's using this device -- not
# generic (doesn't belong in IDENTITY.md) and not personal data about a
# student (doesn't belong in MEMORY.md's category either), but same
# reasoning as MEMORY.md: a live local customization, gitignored.
_NAME_PATH = os.path.join(_PERSONA_DIR, "NAME.txt")
DEFAULT_NAME = "Pixel"

# One extra Gemini call at session end, not after every turn — keeps
# cost down and avoids cluttering memory with trivial small talk.
# Tagged CURRENT/EVENT output (instead of one flat fact-per-line list)
# so a corrected fact (e.g. a renamed companion, a corrected grade)
# replaces the old value in MEMORY.md's Current section instead of
# just piling up next to it forever in a flat append-only list.
_SUMMARIZE_PROMPT = (
    "Below is a transcript of a casual chat between you (Pixel, a desk "
    "companion robot) and a student. Pull out at most 3 short, durable "
    "things worth remembering for next time, each tagged as one of two "
    "kinds:\n"
    "CURRENT: a stable fact about the student that should replace any "
    "previous value of the same kind — name, grade, a recurring "
    "interest. Format: CURRENT: key: value (e.g. "
    "'CURRENT: name: Saravana' or 'CURRENT: interests: robotics, "
    "building things').\n"
    "EVENT: something worth carrying forward from this specific "
    "conversation — an unfinished topic to pick back up, something you "
    "(Pixel) promised to follow up on, a running joke or shared moment. "
    "Format: EVENT: <text>.\n"
    "Skip anything trivial or one-off (like asking about the weather). "
    "One tagged item per line, plain text, no numbering or markdown. If "
    "there's nothing worth keeping, reply with exactly: NOTHING\n\n"
    "Transcript:\n{transcript}"
)


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def _parse_memory(text: str) -> tuple[dict[str, str], list[str]]:
    """Splits MEMORY.md into (current facts, history log). Tolerates the
    old flat `- [date] fact` format with no headers at all — every
    bullet line is kept as history rather than silently dropped, so
    nothing already saved from before this split is lost."""
    current: dict[str, str] = {}
    history: list[str] = []
    if _CURRENT_HEADER not in text and _HISTORY_HEADER not in text:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("-"):
                history.append(line[1:].strip())
        return current, history

    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == _CURRENT_HEADER:
            section = "current"
            continue
        if stripped == _HISTORY_HEADER:
            section = "history"
            continue
        if not stripped.startswith("-"):
            continue
        item = stripped[1:].strip()
        if section == "current" and ":" in item:
            key, value = item.split(":", 1)
            current[key.strip().lower()] = value.strip()
        elif section == "history":
            history.append(item)
    return current, history


def _render_memory(current: dict[str, str], history: list[str]) -> str:
    lines = [_CURRENT_HEADER]
    lines += [f"- {key}: {value}" for key, value in current.items()]
    lines.append("")
    lines.append(_HISTORY_HEADER)
    lines += [f"- {item}" for item in history]
    return "\n".join(lines) + "\n"


def load_context() -> str:
    """Identity + remembered facts, ready to fold into a system instruction."""
    identity = _read(_IDENTITY_PATH)
    current, history = _parse_memory(_read(_MEMORY_PATH))
    parts = []
    if identity:
        parts.append(identity)
    if current:
        lines = "\n".join(f"- {key}: {value}" for key, value in current.items())
        parts.append("What you currently know about the student:\n" + lines)
    if history:
        lines = "\n".join(f"- {item}" for item in history)
        parts.append("What's happened in your ongoing friendship:\n" + lines)
    return "\n\n".join(parts)


def load_name() -> str:
    return _read(_NAME_PATH) or DEFAULT_NAME


def set_name(name: str) -> None:
    name = name.strip()
    if not name:
        return
    os.makedirs(_PERSONA_DIR, exist_ok=True)
    with open(_NAME_PATH, "w", encoding="utf-8") as f:
        f.write(name)


# Common ways someone might actually say this out loud. Not full NLU --
# a tool-call-based approach (the model itself deciding when the intent
# is "rename me") would handle phrasing variety much better, but that's
# unverified new protocol surface; this is the simpler, already-provable
# option for a first version.
#
# Broadened after two real, distinct phrasings slipped through the
# original pattern list in actual use ("I need to name you as Chitty",
# "I changed your name to Chitti") -- neither matched "your name is"/
# "I'll call you"/etc. Still just a pattern list, not understanding, so
# this will keep needing phrases added as new ones are found missed.
_RENAME_PATTERN = re.compile(
    r"(?:"
    r"your (?:new )?name is(?: now)?|"
    r"from now on,? your name is|"
    r"you(?:'re| are) now called|"
    r"let'?s call you|"
    r"name yourself|"
    r"i(?:'ll| will) call you|"
    r"i(?:'m| am) (?:going to )?call(?:ing)? you|"
    r"i(?:'ve| have) changed your name to|"
    r"i changed your name to|"
    r"i(?:'m| am) chang(?:e|ing) your name to|"
    r"i (?:need|want) to (?:name|call|rename) you(?: as)?|"
    r"i(?:'m| am) naming you"
    r")\s+([A-Za-z][A-Za-z\-']{1,20})\b",
    re.IGNORECASE,
)


def detect_rename_request(text: str) -> str | None:
    """Returns the requested new name if `text` contains an explicit
    rename phrase, else None. Checked against the student's own
    transcribed speech, not Pixel's replies."""
    match = _RENAME_PATTERN.search(text)
    if not match:
        return None
    candidate = match.group(1).strip()
    return candidate[:1].upper() + candidate[1:]


def remember_current(key: str, value: str) -> None:
    """Upserts one durable fact into MEMORY.md's Current section — a
    repeat key (e.g. 'name') replaces the old value instead of piling up
    next to it, fixing the old flat-list behavior where a corrected fact
    just sat alongside the stale one forever."""
    key = key.strip().lower()
    value = value.strip()
    if not key or not value:
        return
    os.makedirs(_PERSONA_DIR, exist_ok=True)
    current, history = _parse_memory(_read(_MEMORY_PATH))
    current[key] = value
    with open(_MEMORY_PATH, "w", encoding="utf-8") as f:
        f.write(_render_memory(current, history))


def remember_event(fact: str) -> None:
    """Appends one dated, one-off item to MEMORY.md's History section —
    unfinished topics, promises, shared moments. Always additive, same
    as the old flat-list `remember()` behavior."""
    fact = fact.strip()
    if not fact:
        return
    os.makedirs(_PERSONA_DIR, exist_ok=True)
    current, history = _parse_memory(_read(_MEMORY_PATH))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    history.append(f"[{timestamp}] {fact}")
    with open(_MEMORY_PATH, "w", encoding="utf-8") as f:
        f.write(_render_memory(current, history))


def save_transcript(transcript: list[str]) -> None:
    """Raw session text to _TRANSCRIPT_DIR, before summarization is even
    attempted — a safety net so a crashed/failed summarization call
    doesn't lose the conversation outright. Best-effort: a write failure
    here must never block the session from ending normally."""
    if not transcript:
        return
    try:
        os.makedirs(_TRANSCRIPT_DIR, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = os.path.join(_TRANSCRIPT_DIR, f"{timestamp}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(transcript) + "\n")
    except OSError:
        logger.exception("failed to save raw transcript")


def apply_summary(text: str) -> None:
    """Routes one summarization reply's CURRENT:/EVENT: tagged lines to
    the right MEMORY.md section. A line the model didn't tag (format
    drift) is still kept, as an event, rather than silently dropped."""
    text = (text or "").strip()
    if not text or text.upper() == "NOTHING":
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("current:"):
            parts = line.split(":", 2)
            if len(parts) == 3:
                remember_current(parts[1], parts[2])
                continue
        if lowered.startswith("event:"):
            remember_event(line.split(":", 1)[1])
            continue
        remember_event(line)


def summarize_and_remember(chat, transcript: list[str]) -> None:
    """One cheap call at session end: ask the model what's worth keeping.

    `chat` is the same google-genai chat session already used for the
    conversation (reuses its model/config) — a plain one-off message, not
    part of the ongoing back-and-forth history the student sees.
    """
    if not transcript:
        return
    save_transcript(transcript)
    prompt = _SUMMARIZE_PROMPT.format(transcript="\n".join(transcript))
    try:
        response = chat.send_message(prompt)
        text = (response.text or "").strip()
    except Exception:
        logger.exception("memory summarization failed")
        return
    apply_summary(text)
