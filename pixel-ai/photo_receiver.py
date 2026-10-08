"""Flask server for photo input: student photographs a problem, Pixel explains it.

Run alongside pixel_main.py (see pixel_main's background thread) so a
photo can arrive while Pixel is also waiting on keyboard input.
"""
import logging

from flask import Flask, jsonify, request

import pixel_brain
import pixel_tts
from pixel_face import face, STATE_THINKING, STATE_TALKING, STATE_IDLE

logger = logging.getLogger(__name__)

app = Flask(__name__)

_ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


@app.post("/photo")
def receive_photo():
    if "photo" not in request.files:
        return jsonify({"error": "missing 'photo' file field"}), 400

    photo = request.files["photo"]
    content_type = photo.content_type or "application/octet-stream"
    if content_type not in _ALLOWED_CONTENT_TYPES:
        return jsonify({"error": f"unsupported file type: {content_type}"}), 400

    question = request.form.get("question", "Can you explain this problem?")

    face.set_state(STATE_THINKING)
    try:
        image_url = pixel_brain.upload_image(photo.read(), photo.filename or "photo.jpg", content_type)
        result = pixel_brain.ask(question, image_url=image_url)
        reply = result.get("reply", "")
    except Exception:
        logger.exception("Photo explanation failed")
        face.set_state(STATE_IDLE)
        return jsonify({"error": "failed to get an explanation"}), 502

    face.set_state(STATE_TALKING)
    pixel_tts.speak(reply)
    face.set_state(STATE_IDLE)

    return jsonify({"reply": reply})


def run(host: str = "0.0.0.0", port: int = 5005) -> None:
    app.run(host=host, port=port)
