"""Pixel AI — main entry point (Phase 1: keyboard input, HDMI face, gTTS).

Commands:
  <any question>       -> text explanation via /api/chat/send, spoken aloud
  video: <word problem> -> async Manim clip via /api/public/v1/videos/generate,
                            prints the resulting video_url (no local player yet)
  game: <topic>         -> reports that game generation isn't available yet
  quit / exit           -> shuts down
"""
import logging
import threading

import photo_receiver
import pixel_brain
import pixel_game
import pixel_tts
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING, STATE_HAPPY
from pixel_listen import listen

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handle_question(text: str) -> None:
    face.set_state(STATE_THINKING)
    try:
        result = pixel_brain.ask(text)
        reply = result.get("reply", "")
    except Exception:
        logger.exception("chat/send failed")
        face.set_state(STATE_IDLE)
        print("Sorry, I couldn't reach LearnX.")
        return

    face.set_state(STATE_TALKING)
    pixel_tts.speak(reply)
    face.set_state(STATE_HAPPY)
    print(f"Pixel: {reply}")


def handle_video(prompt: str) -> None:
    face.set_state(STATE_THINKING)
    try:
        video_id = pixel_brain.request_video(prompt)
        result = pixel_brain.poll_video(video_id)
    except Exception:
        logger.exception("video generation failed")
        face.set_state(STATE_IDLE)
        print("Sorry, the animation didn't come through.")
        return

    face.set_state(STATE_HAPPY)
    if result.get("status") == "done" and result.get("video_url"):
        print(f"Pixel: Your animation is ready -> {result['video_url']}")
        pixel_tts.speak("Your animation is ready. Check the screen.")
    else:
        print(f"Pixel: Animation failed: {result.get('error_message')}")


def handle_game(topic: str) -> None:
    game = pixel_game.generate_game(topic)
    if game is None:
        print("Pixel: I can't generate games yet — that part isn't built.")
        pixel_tts.speak("Sorry, I can't make games yet.")


def main() -> None:
    face.start()
    threading.Thread(target=photo_receiver.run, daemon=True).start()

    print("Pixel is listening. Type a question, 'video: ...', 'game: ...', or 'quit'.")
    try:
        while True:
            face.set_state(STATE_LISTENING)
            text = listen()
            if not text:
                continue
            if text.lower() in ("quit", "exit"):
                break
            elif text.lower().startswith("video:"):
                handle_video(text[len("video:"):].strip())
            elif text.lower().startswith("game:"):
                handle_game(text[len("game:"):].strip())
            else:
                handle_question(text)
    finally:
        face.set_state(STATE_IDLE)
        face.stop()


if __name__ == "__main__":
    main()
