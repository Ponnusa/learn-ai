"""Pixel's discussion mode: chunked, paced delivery of any reply.

Standalone, like pixel_ladder.py — only imports the existing
face/tts/listen/brain modules, never edits them.

The backend's own guided-discovery ("ladder") logic only sometimes asks a
real question and waits (ladder_depth > 0) — plenty of conceptual
questions still just get a full direct explanation. This mode doesn't
depend on that happening: it splits ANY reply into its own natural
structure (the ### headings / --- dividers the backend already tends to
use for longer explanations — a short answer with neither stays one
chunk) and delivers one piece at a time, checking in between pieces
instead of narrating one long block. A plain "continue" just advances to
the next piece with no network call; anything substantive gets sent back
to the backend as the next turn in the SAME conversation, so the student
can genuinely branch the discussion instead of just clicking through a
fixed script.
"""
import logging
import re

import pixel_brain
import pixel_tts
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING, STATE_HAPPY
from pixel_listen import listen

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_CONTINUE_WORDS = ("", "continue", "go on", "next", "more", "yes", "ok", "okay")
_STOP_WORDS = ("stop", "quit", "exit")

_HR_RE = re.compile(r"\n\s*-{3,}\s*\n")
_HEADING_SPLIT_RE = re.compile(r"(?=^#{1,6}\s+.+$)", re.MULTILINE)
_HEADING_MARK_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_LATEX_DELIM_RE = re.compile(r"\$\$?|\\\[|\\\]|\\\(|\\\)")
# \mathrm{m/s^2} -> m/s^2 (first-level wrapper only, no nested-brace math)
_LATEX_CMD_WRAPPER_RE = re.compile(r"\\[a-zA-Z]+\{([^{}]*)\}")
# Leftover bare commands like \, \cdot \times once their wrapper is gone
_LATEX_BARE_CMD_RE = re.compile(r"\\[a-zA-Z]+|\\[,;:!]")
_MD_NOISE_RE = re.compile(r"[*_`]{1,3}")
_BULLET_RE = re.compile(r"^[\-\*]\s+", re.MULTILINE)


def chunk_reply(text: str) -> list[str]:
    """Split a reply into discussion-sized pieces using its own structure."""
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    for block in _HR_RE.split(text):
        block = block.strip()
        if not block:
            continue
        for part in _HEADING_SPLIT_RE.split(block):
            part = part.strip()
            if part:
                chunks.append(part)
    return chunks or [text]


def _clean_for_speech(text: str) -> str:
    """Rough local markdown/LaTeX stripping so gTTS doesn't read out
    literal asterisks, hashes and dollar signs on a single chunk.

    Not the backend's GPT-4o-mini cleanup (that endpoint only voices a
    whole stored message, not a partial chunk) — formula pronunciation
    stays rougher than that; good enough for pacing, not perfect.
    """
    text = _HEADING_MARK_RE.sub("", text)
    text = _LATEX_DELIM_RE.sub("", text)
    text = _LATEX_CMD_WRAPPER_RE.sub(r"\1", text)
    text = _LATEX_BARE_CMD_RE.sub(" ", text)
    text = _MD_NOISE_RE.sub("", text)
    text = _BULLET_RE.sub("", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _ask(message: str, conversation_id: str | None) -> tuple[list[str], str | None]:
    result = pixel_brain.ask(message, conversation_id=conversation_id)
    return chunk_reply(result.get("reply", "")), result.get("conversation_id")


def run_discussion(topic: str) -> None:
    conversation_id = None
    message = topic
    pending: list[str] = []

    while True:
        if not pending:
            face.set_state(STATE_THINKING)
            try:
                pending, conversation_id = _ask(message, conversation_id)
            except Exception:
                logger.exception("chat/send failed")
                face.set_state(STATE_IDLE)
                print("Sorry, I couldn't reach LearnX.")
                return
            if not pending:
                face.set_state(STATE_IDLE)
                return

        chunk = pending.pop(0)
        face.set_state(STATE_TALKING)
        print(f"Pixel: {chunk}")
        pixel_tts.speak(_clean_for_speech(chunk))

        face.set_state(STATE_LISTENING)
        if pending:
            print("(enter to continue, or ask something)")
        else:
            print("(say more to keep exploring, ask anything else, or 'stop')")
        answer = listen(prompt="You: ")

        if answer.lower() in _STOP_WORDS:
            face.set_state(STATE_IDLE)
            return
        if answer.lower() in _CONTINUE_WORDS:
            continue

        # Substantive input — abandon any leftover pieces of the old reply
        # and treat this as the next real turn in the same conversation.
        pending = []
        message = answer


def main() -> None:
    face.start()
    print("Pixel discussion mode. Type a topic, or 'quit'.")
    try:
        while True:
            face.set_state(STATE_LISTENING)
            topic = listen(prompt="Topic: ")
            if not topic:
                continue
            if topic.lower() in _STOP_WORDS:
                break
            run_discussion(topic)
    finally:
        face.set_state(STATE_IDLE)
        face.stop()


if __name__ == "__main__":
    main()
