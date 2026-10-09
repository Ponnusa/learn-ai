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
# Pixel's current name, chosen by whoever's using this device -- not
# generic (doesn't belong in IDENTITY.md) and not personal data about a
# student (doesn't belong in MEMORY.md's category either), but same
# reasoning as MEMORY.md: a live local customization, gitignored.
_NAME_PATH = os.path.join(_PERSONA_DIR, "NAME.txt")
DEFAULT_NAME = "Pixel"

# One extra Gemini call at session end, not after every turn — keeps
# cost down and avoids cluttering memory with trivial small talk.
_SUMMARIZE_PROMPT = (
    "Below is a transcript of a casual chat between you (Pixel, a desk "
    "companion robot) and a student. Pull out at most 3 short, durable "
    "things worth remembering for next time: facts about the student "
    "(name, interests, ongoing projects, things they mentioned caring "
    "about), AND things worth carrying forward from the conversation "
    "itself — an unfinished topic to pick back up, something you "
    "(Pixel) promised to help with or follow up on, a running joke or "
    "shared moment that makes the friendship feel continuous rather "
    "than starting from scratch every time. Skip anything trivial or "
    "one-off (like asking about the weather). One item per line, plain "
    "text, no numbering or markdown. If there's nothing worth keeping, "
    "reply with exactly: NOTHING\n\n"
    "Transcript:\n{transcript}"
)


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def load_context() -> str:
    """Identity + remembered facts, ready to fold into a system instruction."""
    identity = _read(_IDENTITY_PATH)
    memory = _read(_MEMORY_PATH)
    parts = []
    if identity:
        parts.append(identity)
    if memory:
        parts.append("What you remember from before (about the student and your ongoing friendship):\n" + memory)
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


def remember(fact: str) -> None:
    """Append one fact to MEMORY.md, creating the file/folder if needed."""
    fact = fact.strip()
    if not fact:
        return
    os.makedirs(_PERSONA_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(_MEMORY_PATH, "a", encoding="utf-8") as f:
        f.write(f"- [{timestamp}] {fact}\n")


def summarize_and_remember(chat, transcript: list[str]) -> None:
    """One cheap call at session end: ask the model what's worth keeping.

    `chat` is the same google-genai chat session already used for the
    conversation (reuses its model/config) — a plain one-off message, not
    part of the ongoing back-and-forth history the student sees.
    """
    if not transcript:
        return
    prompt = _SUMMARIZE_PROMPT.format(transcript="\n".join(transcript))
    try:
        response = chat.send_message(prompt)
        text = (response.text or "").strip()
    except Exception:
        logger.exception("memory summarization failed")
        return

    if not text or text.upper() == "NOTHING":
        return
    for line in text.splitlines():
        remember(line)
