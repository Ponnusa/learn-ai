"""Pixel's ladder mode: short one-to-one guided-discovery conversations.

Standalone and separate from pixel_main.py on purpose — this only imports
the existing face/tts/listen modules plus the direct-API/teaching-prompt
modules, never edits them, so it can be run and tested without touching
the already-working keyboard flow.

Used to route through LearnX's /api/chat/send (ADAPTIVE_TEACHING_
INSTRUCTIONS there), but that meant Pixel -> LearnX -> OpenAI -> LearnX
-> Pixel, two network hops for every single turn, when Pixel can just
call OpenAI directly. Switched to pixel_direct_llm.py +
pixel_teaching_prompt.py (same guided-discovery behavior, ported as a
standalone prompt, no LearnX round-trip) — see those files' docstrings.
Chains are open-ended by the prompt's own design (no min/max enforced);
_MAX_TURNS below is purely a defensive cap on this client, not a real
constraint.
"""
import logging

import pixel_direct_llm
import pixel_teaching_prompt
import pixel_tts
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING, STATE_HAPPY
from pixel_listen import listen

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_MAX_TURNS = 15
_BAIL_OUT_PHRASES = ("stop", "skip", "just tell me")


def _say(reply: str) -> None:
    print(f"Pixel: {reply}")
    pixel_tts.speak(reply)


def run_topic(topic: str) -> None:
    """One short guided-discovery conversation about a single topic."""
    messages = [{"role": "user", "content": topic}]

    for _ in range(_MAX_TURNS):
        face.set_state(STATE_THINKING)
        try:
            raw_reply, _model = pixel_direct_llm.ask(messages, pixel_teaching_prompt.FULL_PROMPT)
        except Exception:
            logger.exception("direct LLM call failed")
            face.set_state(STATE_IDLE)
            print("Sorry, I couldn't reach the AI right now.")
            return

        reply, _depth, waiting = pixel_teaching_prompt.strip_markers(raw_reply)
        messages.append({"role": "assistant", "content": reply})

        face.set_state(STATE_TALKING)
        _say(reply)

        if not waiting:
            # The prompt resolved the chain (or never started one) --
            # this turn's reply is a direct/final answer, not a question.
            face.set_state(STATE_HAPPY)
            return

        face.set_state(STATE_LISTENING)
        answer = listen(prompt="You: ")
        # Mirrors the prompt's own documented bail-out phrasing so a
        # student who wants out gets the same "just tell me" shortcut
        # the system prompt already honors.
        message = "Just tell me the answer." if answer.lower() in _BAIL_OUT_PHRASES else answer
        messages.append({"role": "user", "content": message})

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
