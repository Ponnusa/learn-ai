"""Parent Controls local web UI (spec section 3.2.H; decisions 0002,
0003): PIN-gated, LAN-only, served by the robot itself -- same Flask-
on-a-background-thread pattern as pixel-ai/photo_receiver.py.

Not built here, and genuinely not buildable/verifiable without real
network/radio hardware: mDNS advertisement (`chitti.local`) and the
first-boot setup-hotspot onboarding flow (architecture.md's Parent
Controls section). This module is the web app itself, assumed to be
served on whatever address the device ends up reachable at.

CSRF protection is hand-rolled (a per-session token checked on every
POST) rather than adding a dependency, closing the gap flagged in
docs/security_threat_model.md for exactly this feature.
"""
import functools
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for

from companion_robot.engagement.repository import EngagementRepository
from companion_robot.lullabies.repository import LullabyRepository
from companion_robot.lullabies.schema import LullabyRecord
from companion_robot.memory.repository import MemoryRepository
from companion_robot.transcripts.repository import TranscriptRepository

from .auth import PinRepository, RateLimiter, load_or_create_secret_key
from .profiles import ChildProfile, ChildProfileRepository
from .stories import StoryRecord, StoryRepository

# 20MB -- a generous ceiling for a single lullaby MP3, cheap guard
# against a huge accidental upload filling up the Pi's limited storage.
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def create_app(
    conn: sqlite3.Connection,
    secret_key_path: str,
    lullabies_dir: Path | None = None,
    rate_limiter: RateLimiter | None = None,
) -> Flask:
    app = Flask(__name__)
    app.secret_key = load_or_create_secret_key(secret_key_path)
    app.config["MAX_CONTENT_LENGTH"] = _MAX_UPLOAD_BYTES

    pins = PinRepository(conn)
    profiles = ChildProfileRepository(conn)
    stories = StoryRepository(conn)
    memories = MemoryRepository(conn)
    engagement = EngagementRepository(conn)
    transcripts = TranscriptRepository(conn)
    lullabies = LullabyRepository(conn)
    lullabies_dir = Path(lullabies_dir) if lullabies_dir is not None else Path("data/lullabies")
    lullabies_dir.mkdir(parents=True, exist_ok=True)
    limiter = rate_limiter or RateLimiter()

    def _csrf_token() -> str:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return session["csrf_token"]

    app.jinja_env.globals["csrf_token"] = _csrf_token

    def _csrf_valid() -> bool:
        token = session.get("csrf_token")
        return token is not None and request.form.get("csrf_token") == token

    def requires_auth(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("authenticated"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    @app.get("/")
    def index():
        if not pins.is_set():
            return redirect(url_for("setup"))
        if session.get("authenticated"):
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if pins.is_set():
            return redirect(url_for("login"))
        if request.method == "POST":
            if not _csrf_valid():
                return "Invalid request.", 400
            pin = request.form.get("pin", "")
            confirm = request.form.get("confirm", "")
            if not pin or pin != confirm:
                return render_template("setup.html", error="PINs did not match."), 400
            pins.set_pin(pin)
            return redirect(url_for("login"))
        return render_template("setup.html", error=None)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not pins.is_set():
            return redirect(url_for("setup"))
        if limiter.is_locked_out():
            return (
                render_template(
                    "login.html",
                    error=f"Too many attempts. Try again in {limiter.seconds_remaining()}s.",
                ),
                429,
            )
        if request.method == "POST":
            if not _csrf_valid():
                return "Invalid request.", 400
            pin = request.form.get("pin", "")
            if pins.verify(pin):
                limiter.record_success()
                session["authenticated"] = True
                return redirect(url_for("dashboard"))
            limiter.record_failure()
            return render_template("login.html", error="Incorrect PIN."), 401
        return render_template("login.html", error=None)

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/dashboard")
    @requires_auth
    def dashboard():
        return render_template(
            "dashboard.html",
            profiles=profiles.list_all(),
            stories=stories.list_all(),
            lullabies=lullabies.list_all(),
        )

    @app.route("/profiles", methods=["GET", "POST"])
    @requires_auth
    def profiles_view():
        if request.method == "POST":
            if not _csrf_valid():
                return "Invalid request.", 400
            name = request.form.get("name", "").strip()
            age = request.form.get("age", "").strip()
            if not name or not age.isdigit():
                return (
                    render_template(
                        "profiles.html",
                        profiles=profiles.list_all(),
                        error="Name and a numeric age are required.",
                    ),
                    400,
                )
            now = datetime.now(timezone.utc)
            profiles.create(
                ChildProfile(
                    id=secrets.token_hex(8),
                    name=name,
                    age=int(age),
                    created_at=now,
                    updated_at=now,
                )
            )
            return redirect(url_for("profiles_view"))
        return render_template("profiles.html", profiles=profiles.list_all(), error=None)

    @app.post("/profiles/<profile_id>/delete")
    @requires_auth
    def delete_profile(profile_id):
        if not _csrf_valid():
            return "Invalid request.", 400
        profiles.delete(profile_id)
        return redirect(url_for("profiles_view"))

    @app.route("/profiles/<profile_id>/edit", methods=["GET", "POST"])
    @requires_auth
    def edit_profile(profile_id):
        profile = profiles.get(profile_id)
        if profile is None:
            return redirect(url_for("profiles_view"))
        if request.method == "POST":
            if not _csrf_valid():
                return "Invalid request.", 400
            name = request.form.get("name", "").strip()
            age = request.form.get("age", "").strip()
            speed_raw = request.form.get("speech_speed", "").strip()
            try:
                speed = float(speed_raw)
            except ValueError:
                speed = None
            # OpenAI's TTS API accepts 0.25-4.0 (voice/tts_openai.py) --
            # validated here too so a bad value gets a clear in-page
            # error now, not a confusing API failure during a live
            # conversation later.
            if not name or not age.isdigit() or speed is None or not (0.25 <= speed <= 4.0):
                return (
                    render_template(
                        "edit_profile.html",
                        profile=profile,
                        error="Name, a numeric age, and a speech speed between 0.25 and 4.0 are required.",
                    ),
                    400,
                )
            profiles.update(profile_id, name=name, age=int(age), speech_speed=speed)
            return redirect(url_for("profiles_view"))
        return render_template("edit_profile.html", profile=profile, error=None)

    @app.route("/stories", methods=["GET", "POST"])
    @requires_auth
    def stories_view():
        if request.method == "POST":
            if not _csrf_valid():
                return "Invalid request.", 400
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            if not title or not content:
                return (
                    render_template(
                        "stories.html",
                        stories=stories.list_all(),
                        error="Title and content are required.",
                    ),
                    400,
                )
            stories.create(
                StoryRecord(
                    id=secrets.token_hex(8),
                    title=title,
                    content=content,
                    created_at=datetime.now(timezone.utc),
                )
            )
            return redirect(url_for("stories_view"))
        return render_template("stories.html", stories=stories.list_all(), error=None)

    @app.post("/stories/<story_id>/delete")
    @requires_auth
    def delete_story(story_id):
        if not _csrf_valid():
            return "Invalid request.", 400
        stories.delete(story_id)
        return redirect(url_for("stories_view"))

    @app.route("/lullabies", methods=["GET", "POST"])
    @requires_auth
    def lullabies_view():
        if request.method == "POST":
            if not _csrf_valid():
                return "Invalid request.", 400
            title = request.form.get("title", "").strip()
            audio = request.files.get("audio")
            valid_upload = (
                audio is not None
                and audio.filename
                and audio.filename.lower().endswith(".mp3")
            )
            if not title or not valid_upload:
                return (
                    render_template(
                        "lullabies.html",
                        lullabies=lullabies.list_all(),
                        error="Title and an .mp3 file are required.",
                    ),
                    400,
                )
            lullaby_id = secrets.token_hex(8)
            # The file's path is always derived from this id, never
            # from the parent-supplied filename -- see lullabies/
            # __init__.py for why (sidesteps path-traversal/collision
            # risk entirely rather than needing to sanitize anything).
            audio.save(lullabies_dir / f"{lullaby_id}.mp3")
            lullabies.create(
                LullabyRecord(
                    id=lullaby_id,
                    title=title,
                    created_at=datetime.now(timezone.utc),
                )
            )
            return redirect(url_for("lullabies_view"))
        return render_template("lullabies.html", lullabies=lullabies.list_all(), error=None)

    @app.post("/lullabies/<lullaby_id>/delete")
    @requires_auth
    def delete_lullaby(lullaby_id):
        if not _csrf_valid():
            return "Invalid request.", 400
        lullabies.delete(lullaby_id)
        (lullabies_dir / f"{lullaby_id}.mp3").unlink(missing_ok=True)
        return redirect(url_for("lullabies_view"))

    @app.get("/profiles/<profile_id>/memories")
    @requires_auth
    def profile_memories(profile_id):
        return render_template(
            "memories.html", profile_id=profile_id, records=memories.list_for_child(profile_id)
        )

    @app.post("/profiles/<profile_id>/memories/<memory_id>/delete")
    @requires_auth
    def delete_memory(profile_id, memory_id):
        if not _csrf_valid():
            return "Invalid request.", 400
        memories.delete(memory_id, profile_id)
        return redirect(url_for("profile_memories", profile_id=profile_id))

    @app.get("/profiles/<profile_id>/engagement")
    @requires_auth
    def profile_engagement(profile_id):
        return render_template(
            "engagement.html",
            profile_id=profile_id,
            sessions=engagement.list_for_child(profile_id),
        )

    @app.get("/profiles/<profile_id>/transcripts")
    @requires_auth
    def profile_transcripts(profile_id):
        return render_template(
            "transcripts.html",
            profile_id=profile_id,
            records=transcripts.list_for_child(profile_id),
        )

    @app.post("/profiles/<profile_id>/transcripts/<transcript_id>/delete")
    @requires_auth
    def delete_transcript(profile_id, transcript_id):
        if not _csrf_valid():
            return "Invalid request.", 400
        transcripts.delete(transcript_id, profile_id)
        return redirect(url_for("profile_transcripts", profile_id=profile_id))

    return app


def main() -> None:
    """Standalone entry point for manual LAN-reachability testing --
    real deployment would run this inside app.py's own process
    lifecycle, not as a separate script. Persists to a real SQLite
    file (chitti/data/chitti.db), not ":memory:", so profiles/stories/
    the PIN survive a restart. Binds 0.0.0.0 so it's actually reachable
    from another device on the LAN, matching the LAN-only design --
    never bind this to a public interface. debug=False is explicit,
    not just the default: Werkzeug's debugger allows arbitrary code
    execution from anyone who can reach it, which is never acceptable
    here even on a "trusted" home network.
    """
    from pathlib import Path

    from companion_robot.storage.sqlite import connect

    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    conn = connect(data_dir / "chitti.db")
    app = create_app(
        conn,
        secret_key_path=data_dir / "session_secret.key",
        lullabies_dir=data_dir / "lullabies",
    )
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
