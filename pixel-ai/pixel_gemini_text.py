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

from dotenv import load_dotenv
from google import genai
from google.genai import types

import pixel_tts
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING, STATE_HAPPY
from pixel_listen import listen

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
# A plain chat model, not a Live one — no audio streaming needed here.
MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")

PERSONA = (
    "You're Pixel, a friendly, casual desk companion robot for a student. "
    "Keep replies short and conversational, like a real spoken chat with "
    "a curious friend, not a lecture. Warm, a little playful, genuinely "
    "interested in what the student says. Plain spoken sentences only — "
    "no markdown, no bullet points, no headings, no LaTeX — this gets "
    "read aloud by a text-to-speech engine that can't pronounce symbols."
)

_STOP_WORDS = ("stop", "quit", "exit")


def main() -> None:
    client = genai.Client(api_key=GEMINI_API_KEY)
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=PERSONA),
    )

    face.start()
    print("Pixel (text mode, Gemini — LearnX paused). Type to chat, or 'quit'.")
    try:
        while True:
            face.set_state(STATE_LISTENING)
            text = listen(prompt="You: ")
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
                face.set_state(STATE_IDLE)
                continue

            face.set_state(STATE_TALKING)
            print(f"Pixel: {reply}")
            pixel_tts.speak(reply)
            face.set_state(STATE_HAPPY)
    finally:
        face.set_state(STATE_IDLE)
        face.stop()


if __name__ == "__main__":
    main()
