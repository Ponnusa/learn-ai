"""Pixel's casual conversational layer via Gemini — keyboard fallback.

Same intent as pixel_gemini.py (casual chat via Gemini, LearnX paused),
but for when there's no working mic yet: plain text in via keyboard,
Gemini's regular chat API (not Live/audio streaming), spoken reply out
via the existing gTTS+mpg123 pipeline. Standalone, like every other
pixel_*.py mode script — doesn't import config.py, only
pixel_face/pixel_tts/pixel_listen.

Uses client.chats.create()/chat.send_message() for built-in multi-turn
history instead of managing a messages list by hand.
"""
import logging
import os
import queue
import threading

from dotenv import load_dotenv
from google import genai
from google.genai import types

import pixel_memory
import pixel_tts
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING
from pixel_listen import listen

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
# A plain chat model, not a Live one — no audio streaming needed here.
# gemini-2.5-flash 404s now: Google's own error says it's "no longer
# available to new users" and points at gemini-3.8-flash directly.
MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")

PERSONA = (
    "You're Pixel, a friendly, casual desk companion robot for a student. "
    "Keep replies short and conversational, like a real spoken chat with "
    "a curious friend, not a lecture. Warm, a little playful, genuinely "
    "interested in what the student says. Plain spoken sentences only — "
    "no markdown, no bullet points, no headings, no LaTeX — this gets "
    "read aloud by a text-to-speech engine that can't pronounce symbols."
)

_STOP_WORDS = ("stop", "quit", "exit")


def _speak_and_listen(text: str | None, prompt: str) -> str:
    """Speak (if there's anything to say) and listen at the same time.

    Typing while Pixel is still talking used to leave mpg123 and the
    keyboard both contending for the terminal, which could hang or loop
    instead of cleanly interrupting — same barge-in fix already used in
    pixel_discussion.py. If text is None/empty (the very first turn),
    this is just a plain listen().
    """
    if not text:
        return listen(prompt=prompt)

    answers: "queue.Queue[str]" = queue.Queue()
    state = {"proc": None, "path": None, "cancelled": False}
    lock = threading.Lock()

    def _speak_worker() -> None:
        proc, path = pixel_tts.speak_async(text)
        with lock:
            if state["cancelled"]:
                pixel_tts.stop(proc)
                pixel_tts.cleanup_speech(path)
            else:
                state["proc"], state["path"] = proc, path

    threading.Thread(target=_speak_worker, daemon=True).start()
    threading.Thread(target=lambda: answers.put(listen(prompt=prompt)), daemon=True).start()

    while True:
        try:
            answer = answers.get(timeout=0.15)
            break
        except queue.Empty:
            continue

    with lock:
        state["cancelled"] = True
        pixel_tts.stop(state["proc"])
        pixel_tts.cleanup_speech(state["path"])
    return answer


def main() -> None:
    client = genai.Client(api_key=GEMINI_API_KEY)
    system_instruction = PERSONA
    remembered = pixel_memory.load_context()
    if remembered:
        system_instruction = f"{PERSONA}\n\n{remembered}"
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )

    face.start()
    print("Pixel (text mode, Gemini — LearnX paused). Type to chat, or 'quit'.")
    reply = None  # what to speak while listening for the next line; None on turn 1
    transcript: list[str] = []
    try:
        while True:
            face.set_state(STATE_TALKING if reply else STATE_LISTENING)
            text = _speak_and_listen(reply, prompt="You: ")
            reply = None
            if not text:
                continue
            if text.lower() in _STOP_WORDS:
                break

            face.set_state(STATE_THINKING)
            try:
                response = chat.send_message(text)
                reply = response.text or ""
            except Exception:
                logger.exception("Gemini send_message failed")
                print("Sorry, I couldn't reach Gemini.")
                continue

            print(f"Pixel: {reply}")
            transcript.append(f"Student: {text}")
            transcript.append(f"Pixel: {reply}")
    finally:
        pixel_memory.summarize_and_remember(chat, transcript)
        face.set_state(STATE_IDLE)
        face.stop()


if __name__ == "__main__":
    main()
