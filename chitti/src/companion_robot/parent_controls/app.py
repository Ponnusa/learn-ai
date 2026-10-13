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

from flask import Flask, redirect, render_template, request, session, url_for

from companion_robot.memory.repository import MemoryRepository

from .auth import PinRepository, RateLimiter, load_or_create_secret_key
from .profiles import ChildProfile, ChildProfileRepository
from .stories import StoryRecord, StoryRepository


def create_app(
    conn: sqlite3.Connection,
    secret_key_path: str,
    rate_limiter: RateLimiter | None = None,
) -> Flask:
    app = Flask(__name__)
    app.secret_key = load_or_create_secret_key(secret_key_path)

    pins = PinRepository(conn)
    profiles = ChildProfileRepository(conn)
    stories = StoryRepository(conn)
    memories = MemoryRepository(conn)
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
            "dashboard.html", profiles=profiles.list_all(), stories=stories.list_all()
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

    return app
