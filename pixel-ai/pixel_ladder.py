"""Pixel's ladder mode: short one-to-one guided-discovery conversations.

Standalone and separate from pixel_main.py on purpose — this only imports
the existing face/tts/listen/brain modules, never edits them, so it can
be run and tested without touching the already-working keyboard flow.

The "ladder" behavior isn't something Pixel implements itself: the
backend's system prompt already decides, on every /api/chat/send reply,
whether to answer directly or ask exactly one guiding question and wait
(ladder_depth > 0 — see backend/services/prompt_builder.py's
ADAPTIVE_TEACHING_INSTRUCTIONS). The only thing a client needs to do to
turn that into a real back-and-forth instead of one-shot Q&A is keep
reusing the same conversation_id turn after turn. No mode flag, no
separate endpoint. Chains are open-ended by backend design (no min/max
enforced); _MAX_TURNS below is purely a defensive cap on this client, not
a real constraint from the backend.
"""
import logging

import pixel_brain
import pixel_tts
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING, STATE_HAPPY
from pixel_listen import listen

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_MAX_TURNS = 15
_BAIL_OUT_PHRASES = ("stop", "skip", "just tell me")


def _say(reply: str, message_id: str | None) -> None:
    print(f"Pixel: {reply}")
    try:
        pixel_tts.speak_reply_audio(pixel_brain.get_message_audio(message_id))
    except Exception:
        logger.exception("chat audio fetch failed, falling back to gTTS")
        pixel_tts.speak(reply)


def run_topic(topic: str) -> None:
    """One short guided-discovery conversation about a single topic."""
    conversation_id = None
    message = topic

    for _ in range(_MAX_TURNS):
        face.set_state(STATE_THINKING)
        try:
            result = pixel_brain.ask(message, conversation_id=conversation_id)
        except Exception:
            logger.exception("chat/send failed")
            face.set_state(STATE_IDLE)
            print("Sorry, I couldn't reach LearnX.")
            return

        conversation_id = result.get("conversation_id")
        reply = result.get("reply", "")
        ladder_depth = result.get("ladder_depth") or 0

        face.set_state(STATE_TALKING)
        _say(reply, result.get("message_id"))

        if not ladder_depth:
            # Backend resolved the chain (or never started one) — this
            # turn's reply is a direct/final answer, not a question.
            face.set_state(STATE_HAPPY)
            return

        face.set_state(STATE_LISTENING)
        answer = listen(prompt="You: ")
        # Mirrors the backend's own documented bail-out phrasing so a
        # student who wants out gets the same "just tell me" shortcut the
        # system prompt already honors server-side.
        message = "Just tell me the answer." if answer.lower() in _BAIL_OUT_PHRASES else answer

    face.set_state(STATE_IDLE)


def main() -> None:
    face.start()
    print("Pixel ladder mode. Type a topic for a short back-and-forth, or 'quit'.")
    try:
        while True:
            face.set_state(STATE_LISTENING)
            topic = listen(prompt="Topic: ")
            if not topic:
                continue
            if topic.lower() in ("quit", "exit"):
                break
            run_topic(topic)
    finally:
        face.set_state(STATE_IDLE)
        face.stop()


if __name__ == "__main__":
    main()
