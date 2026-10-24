"""Unit tests for companion_robot.parent_controls.app -- uses Flask's
test client against an in-memory SQLite database, no real server, no
real network needed.
"""
import tempfile
from pathlib import Path

import pytest

from companion_robot.parent_controls.app import create_app
from companion_robot.parent_controls.auth import RateLimiter
from companion_robot.storage.sqlite import connect


def _make_app(rate_limiter: RateLimiter | None = None):
    """Returns (app, conn) -- the same connection object create_app()
    builds its repositories on, so tests can seed data directly through
    a repository sharing that exact connection (":memory:" databases
    are per-connection, so a second connect(":memory:") would be an
    entirely separate, empty database)."""
    conn = connect(":memory:")
    tmp_dir = Path(tempfile.mkdtemp())
    secret_path = tmp_dir / "secret.key"
    app = create_app(
        conn,
        secret_key_path=secret_path,
        lullabies_dir=tmp_dir / "lullabies",
        rate_limiter=rate_limiter,
    )
    app.config["TESTING"] = True
    app.config["LULLABIES_DIR"] = tmp_dir / "lullabies"  # test-only, for file-on-disk assertions
    return app, conn


def _get_csrf_token(client) -> str:
    with client.session_transaction() as sess:
        return sess.get("csrf_token") or ""


def _ensure_session_csrf(client) -> str:
    client.get("/login")  # triggers csrf_token() in the template, populating the session
    return _get_csrf_token(client)


def test_index_redirects_to_setup_when_no_pin():
    app, conn = _make_app()
    client = app.test_client()
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/setup" in response.headers["Location"]


def test_setup_creates_pin_and_redirects_to_login():
    app, conn = _make_app()
    client = app.test_client()
    client.get("/setup")
    token = _get_csrf_token(client)

    response = client.post(
        "/setup", data={"pin": "1234", "confirm": "1234", "csrf_token": token}
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_setup_rejects_mismatched_pins():
    app, conn = _make_app()
    client = app.test_client()
    client.get("/setup")
    token = _get_csrf_token(client)

    response = client.post(
        "/setup", data={"pin": "1234", "confirm": "9999", "csrf_token": token}
    )

    assert response.status_code == 400


def test_login_with_correct_pin_authenticates():
    app, conn = _make_app()
    client = app.test_client()
    client.get("/setup")
    token = _get_csrf_token(client)
    client.post("/setup", data={"pin": "1234", "confirm": "1234", "csrf_token": token})

    token = _get_csrf_token(client)
    response = client.post("/login", data={"pin": "1234", "csrf_token": token})

    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_login_with_wrong_pin_rejected():
    app, conn = _make_app()
    client = app.test_client()
    client.get("/setup")
    token = _get_csrf_token(client)
    client.post("/setup", data={"pin": "1234", "confirm": "1234", "csrf_token": token})

    token = _get_csrf_token(client)
    response = client.post("/login", data={"pin": "0000", "csrf_token": token})

    assert response.status_code == 401


def test_login_rate_limited_after_too_many_failures():
    app, conn = _make_app(rate_limiter=RateLimiter(max_attempts=2, lockout_seconds=60))
    client = app.test_client()
    client.get("/setup")
    token = _get_csrf_token(client)
    client.post("/setup", data={"pin": "1234", "confirm": "1234", "csrf_token": token})

    for _ in range(2):
        token = _get_csrf_token(client)
        client.post("/login", data={"pin": "0000", "csrf_token": token})

    response = client.get("/login")
    assert response.status_code == 429


def test_rate_limit_is_server_side_not_reset_by_a_fresh_session():
    """The lockout must survive clearing cookies/starting a new browser
    session -- otherwise an attacker just clears cookies between
    attempts and the limiter does nothing. Proven by hitting the
    lockout with one client, then checking a brand-new test client
    (fresh cookies) against the SAME app instance is still locked out."""
    app, conn = _make_app(rate_limiter=RateLimiter(max_attempts=2, lockout_seconds=60))
    first_client = app.test_client()
    first_client.get("/setup")
    token = _get_csrf_token(first_client)
    first_client.post("/setup", data={"pin": "1234", "confirm": "1234", "csrf_token": token})

    for _ in range(2):
        token = _get_csrf_token(first_client)
        first_client.post("/login", data={"pin": "0000", "csrf_token": token})

    fresh_client = app.test_client()
    response = fresh_client.get("/login")
    assert response.status_code == 429


def test_protected_route_redirects_when_not_authenticated():
    app, conn = _make_app()
    client = app.test_client()
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_post_rejected_without_valid_csrf_token():
    app, conn = _make_app()
    client = app.test_client()
    client.get("/setup")

    response = client.post(
        "/setup", data={"pin": "1234", "confirm": "1234", "csrf_token": "wrong-token"}
    )

    assert response.status_code == 400


def _authenticated_client(app):
    client = app.test_client()
    client.get("/setup")
    token = _get_csrf_token(client)
    client.post("/setup", data={"pin": "1234", "confirm": "1234", "csrf_token": token})
    token = _get_csrf_token(client)
    client.post("/login", data={"pin": "1234", "csrf_token": token})
    return client


def test_create_and_list_child_profile():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)

    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})
    response = client.get("/profiles")

    assert response.status_code == 200
    assert b"Anna" in response.data


def test_delete_child_profile():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})

    response = client.get("/profiles")
    assert b"Anna" in response.data

    from companion_robot.parent_controls.profiles import ChildProfileRepository
    from companion_robot.storage.sqlite import connect as _connect

    # Fetch the real profile id the route created, via a fresh repo on
    # the same connection the app is using internally isn't directly
    # accessible here, so re-derive it from the rendered page instead
    # of poking at app internals.
    import re

    match = re.search(rb'/profiles/([a-f0-9]+)/delete', response.data)
    assert match is not None
    profile_id = match.group(1).decode()

    token = _get_csrf_token(client)
    client.post(f"/profiles/{profile_id}/delete", data={"csrf_token": token})

    response = client.get("/profiles")
    assert b"Anna" not in response.data


def test_create_and_list_story():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)

    client.post(
        "/stories",
        data={"title": "The Fox", "content": "Once upon a time...", "csrf_token": token},
    )
    response = client.get("/stories")

    assert response.status_code == 200
    assert b"The Fox" in response.data


def test_delete_story():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post(
        "/stories",
        data={"title": "The Fox", "content": "Once upon a time...", "csrf_token": token},
    )

    response = client.get("/stories")
    import re

    match = re.search(rb'/stories/([a-f0-9]+)/delete', response.data)
    assert match is not None
    story_id = match.group(1).decode()

    token = _get_csrf_token(client)
    client.post(f"/stories/{story_id}/delete", data={"csrf_token": token})

    response = client.get("/stories")
    assert b"The Fox" not in response.data


def test_create_and_list_lullaby():
    import io

    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)

    client.post(
        "/lullabies",
        data={
            "title": "Hush Little Baby",
            "audio": (io.BytesIO(b"fake mp3 bytes"), "lullaby.mp3"),
            "csrf_token": token,
        },
        content_type="multipart/form-data",
    )
    response = client.get("/lullabies")

    assert response.status_code == 200
    assert b"Hush Little Baby" in response.data
    saved_files = list(app.config["LULLABIES_DIR"].glob("*.mp3"))
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == b"fake mp3 bytes"


def test_lullaby_upload_rejects_non_mp3_file():
    import io

    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)

    response = client.post(
        "/lullabies",
        data={
            "title": "Not Audio",
            "audio": (io.BytesIO(b"not an mp3"), "notes.txt"),
            "csrf_token": token,
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Not Audio" not in client.get("/lullabies").data


def test_delete_lullaby_removes_record_and_file():
    import io
    import re

    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post(
        "/lullabies",
        data={
            "title": "Hush Little Baby",
            "audio": (io.BytesIO(b"fake mp3 bytes"), "lullaby.mp3"),
            "csrf_token": token,
        },
        content_type="multipart/form-data",
    )

    response = client.get("/lullabies")
    match = re.search(rb'/lullabies/([a-f0-9]+)/delete', response.data)
    assert match is not None
    lullaby_id = match.group(1).decode()

    token = _get_csrf_token(client)
    client.post(f"/lullabies/{lullaby_id}/delete", data={"csrf_token": token})

    response = client.get("/lullabies")
    assert b"Hush Little Baby" not in response.data
    assert not (app.config["LULLABIES_DIR"] / f"{lullaby_id}.mp3").exists()


def test_memory_review_lists_and_deletes_records_scoped_to_profile():
    from datetime import datetime, timezone

    from companion_robot.memory.repository import MemoryRepository
    from companion_robot.memory.schema import (
        ConsentStatus,
        MemoryCategory,
        MemoryRecord,
        MemorySource,
    )

    app, conn = _make_app()
    client = _authenticated_client(app)

    # Seed a memory record on the SAME connection create_app() built its
    # own MemoryRepository on -- a second connect(":memory:") would be
    # an entirely separate, empty database, so this only works because
    # _make_app() hands back the exact connection object it passed in.
    memories = MemoryRepository(conn)
    now = datetime.now(timezone.utc)
    memories.create(
        MemoryRecord(
            id="mem-1",
            child_profile_id="anna",
            category=MemoryCategory.PERSONAL_PREFERENCE,
            content="likes dinosaurs",
            created_at=now,
            updated_at=now,
            source=MemorySource.CHILD,
            consent_or_authorization_status=ConsentStatus.GRANTED,
            retention_policy="default",
        )
    )

    response = client.get("/profiles/anna/memories")
    assert b"likes dinosaurs" in response.data

    token = _get_csrf_token(client)
    client.post("/profiles/anna/memories/mem-1/delete", data={"csrf_token": token})

    response = client.get("/profiles/anna/memories")
    assert b"likes dinosaurs" not in response.data
    assert memories.get("mem-1", "anna") is None


def test_memory_review_page_renders_for_a_profile_with_no_memories():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})

    response = client.get("/profiles")
    import re

    match = re.search(rb'/profiles/([a-f0-9]+)/memories', response.data)
    assert match is not None
    profile_id = match.group(1).decode()

    response = client.get(f"/profiles/{profile_id}/memories")
    assert response.status_code == 200


def test_engagement_page_lists_sessions_scoped_to_profile():
    from datetime import datetime, timezone

    from companion_robot.engagement.repository import EngagementRepository
    from companion_robot.engagement.schema import EngagementMode, EngagementSession

    app, conn = _make_app()
    client = _authenticated_client(app)

    # Same shared-connection requirement as the memories test above --
    # a second connect(":memory:") would be an entirely separate database.
    engagement = EngagementRepository(conn)
    now = datetime.now(timezone.utc)
    engagement.create(
        EngagementSession(
            id="eng-1",
            child_profile_id="anna",
            mode=EngagementMode.TEACHABLE_FRIEND,
            turn_count=4,
            word_count=30,
            created_at=now,
        )
    )

    response = client.get("/profiles/anna/engagement")

    assert response.status_code == 200
    assert b"teachable_friend" in response.data
    assert b"30" in response.data


def test_engagement_page_renders_for_a_profile_with_no_sessions():
    app, conn = _make_app()
    client = _authenticated_client(app)

    response = client.get("/profiles/anna/engagement")

    assert response.status_code == 200


def test_transcripts_page_lists_and_deletes_records_scoped_to_profile():
    from datetime import datetime, timezone

    from companion_robot.engagement.schema import EngagementMode
    from companion_robot.memory.schema import ConsentStatus
    from companion_robot.transcripts.repository import TranscriptRepository
    from companion_robot.transcripts.schema import TranscriptRecord

    app, conn = _make_app()
    client = _authenticated_client(app)

    transcripts = TranscriptRepository(conn)
    now = datetime.now(timezone.utc)
    transcripts.create(
        TranscriptRecord(
            id="tr-1",
            child_profile_id="anna",
            mode=EngagementMode.EVERYDAY_COMPANION,
            content="user: I am bored\nassistant: Let's play a game!",
            created_at=now,
            consent_or_authorization_status=ConsentStatus.GRANTED,
            retention_policy="demo",
        )
    )

    response = client.get("/profiles/anna/transcripts")
    assert response.status_code == 200
    assert b"I am bored" in response.data
    assert b"speaker-user" in response.data

    token = _get_csrf_token(client)
    client.post("/profiles/anna/transcripts/tr-1/delete", data={"csrf_token": token})

    response = client.get("/profiles/anna/transcripts")
    assert b"I am bored" not in response.data
    assert transcripts.list_for_child("anna") == []


def test_transcripts_page_renders_for_a_profile_with_no_records():
    app, conn = _make_app()
    client = _authenticated_client(app)

    response = client.get("/profiles/anna/transcripts")

    assert response.status_code == 200


def test_edit_profile_page_shows_current_speech_speed():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})

    response = client.get("/profiles")
    import re

    match = re.search(rb'/profiles/([a-f0-9]+)/edit', response.data)
    assert match is not None
    profile_id = match.group(1).decode()

    response = client.get(f"/profiles/{profile_id}/edit")
    assert response.status_code == 200
    assert b"1.0" in response.data  # default speech_speed shown in the form


def test_edit_profile_updates_speech_speed():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})

    response = client.get("/profiles")
    import re

    profile_id = re.search(rb'/profiles/([a-f0-9]+)/edit', response.data).group(1).decode()

    token = _get_csrf_token(client)
    response = client.post(
        f"/profiles/{profile_id}/edit",
        data={
            "name": "Anna",
            "age": "7",
            "speech_speed": "0.8",
            "reading_pace_wpm": "45",
            "reading_font_size": "28",
            "reading_font_color": "white",
            "csrf_token": token,
        },
    )
    assert response.status_code == 302

    from companion_robot.parent_controls.profiles import ChildProfileRepository

    profiles = ChildProfileRepository(conn)
    assert profiles.get(profile_id).speech_speed == 0.8


def test_edit_profile_updates_interest():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})

    response = client.get("/profiles")
    import re

    profile_id = re.search(rb'/profiles/([a-f0-9]+)/edit', response.data).group(1).decode()

    token = _get_csrf_token(client)
    response = client.post(
        f"/profiles/{profile_id}/edit",
        data={
            "name": "Anna",
            "age": "7",
            "speech_speed": "1.0",
            "interest": "dinosaurs",
            "reading_pace_wpm": "45",
            "reading_font_size": "28",
            "reading_font_color": "white",
            "csrf_token": token,
        },
    )
    assert response.status_code == 302

    from companion_robot.parent_controls.profiles import ChildProfileRepository

    profiles = ChildProfileRepository(conn)
    assert profiles.get(profile_id).interest == "dinosaurs"


def test_edit_profile_rejects_out_of_range_speed():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})

    response = client.get("/profiles")
    import re

    profile_id = re.search(rb'/profiles/([a-f0-9]+)/edit', response.data).group(1).decode()

    token = _get_csrf_token(client)
    response = client.post(
        f"/profiles/{profile_id}/edit",
        data={"name": "Anna", "age": "7", "speech_speed": "9.0", "csrf_token": token},
    )
    assert response.status_code == 400


def test_edit_profile_updates_reading_display_settings():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})

    response = client.get("/profiles")
    import re

    profile_id = re.search(rb'/profiles/([a-f0-9]+)/edit', response.data).group(1).decode()

    token = _get_csrf_token(client)
    response = client.post(
        f"/profiles/{profile_id}/edit",
        data={
            "name": "Anna",
            "age": "7",
            "speech_speed": "1.0",
            "reading_pace_wpm": "60",
            "reading_font_size": "36",
            "reading_font_color": "yellow",
            "csrf_token": token,
        },
    )
    assert response.status_code == 302

    from companion_robot.parent_controls.profiles import ChildProfileRepository

    profile = ChildProfileRepository(conn).get(profile_id)
    assert profile.reading_pace_wpm == 60.0
    assert profile.reading_font_size == 36
    assert profile.reading_font_color == "yellow"


def test_edit_profile_rejects_out_of_range_reading_pace():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})

    response = client.get("/profiles")
    import re

    profile_id = re.search(rb'/profiles/([a-f0-9]+)/edit', response.data).group(1).decode()

    token = _get_csrf_token(client)
    response = client.post(
        f"/profiles/{profile_id}/edit",
        data={
            "name": "Anna",
            "age": "7",
            "speech_speed": "1.0",
            "reading_pace_wpm": "500",
            "reading_font_size": "28",
            "reading_font_color": "white",
            "csrf_token": token,
        },
    )
    assert response.status_code == 400


def test_edit_profile_rejects_an_unlisted_reading_font_color():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})

    response = client.get("/profiles")
    import re

    profile_id = re.search(rb'/profiles/([a-f0-9]+)/edit', response.data).group(1).decode()

    token = _get_csrf_token(client)
    response = client.post(
        f"/profiles/{profile_id}/edit",
        data={
            "name": "Anna",
            "age": "7",
            "speech_speed": "1.0",
            "reading_pace_wpm": "45",
            "reading_font_size": "28",
            "reading_font_color": "purple",  # not in the vetted list
            "csrf_token": token,
        },
    )
    assert response.status_code == 400


def test_edit_profile_updates_preferred_phase():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    profile_id = _create_profile_and_get_id(client, token)

    token = _get_csrf_token(client)
    response = client.post(
        f"/profiles/{profile_id}/edit",
        data={
            "name": "Anna",
            "age": "7",
            "speech_speed": "1.0",
            "reading_pace_wpm": "45",
            "reading_font_size": "28",
            "reading_font_color": "white",
            "preferred_phase": "3",
            "csrf_token": token,
        },
    )
    assert response.status_code == 302

    from companion_robot.parent_controls.profiles import ChildProfileRepository

    assert ChildProfileRepository(conn).get(profile_id).preferred_phase == 3


def test_edit_profile_empty_preferred_phase_means_no_preference():
    """Decision 0104: an explicitly empty selection clears the
    preference back to None (Reading Partner's existing
    LLM-generation-first behavior), same as never having set one."""
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    profile_id = _create_profile_and_get_id(client, token)

    token = _get_csrf_token(client)
    client.post(
        f"/profiles/{profile_id}/edit",
        data={
            "name": "Anna",
            "age": "7",
            "speech_speed": "1.0",
            "reading_pace_wpm": "45",
            "reading_font_size": "28",
            "reading_font_color": "white",
            "preferred_phase": "3",
            "csrf_token": token,
        },
    )

    token = _get_csrf_token(client)
    client.post(
        f"/profiles/{profile_id}/edit",
        data={
            "name": "Anna",
            "age": "7",
            "speech_speed": "1.0",
            "reading_pace_wpm": "45",
            "reading_font_size": "28",
            "reading_font_color": "white",
            "preferred_phase": "",
            "csrf_token": token,
        },
    )

    from companion_robot.parent_controls.profiles import ChildProfileRepository

    assert ChildProfileRepository(conn).get(profile_id).preferred_phase is None


def test_edit_profile_rejects_an_out_of_range_preferred_phase():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    profile_id = _create_profile_and_get_id(client, token)

    token = _get_csrf_token(client)
    response = client.post(
        f"/profiles/{profile_id}/edit",
        data={
            "name": "Anna",
            "age": "7",
            "speech_speed": "1.0",
            "reading_pace_wpm": "45",
            "reading_font_size": "28",
            "reading_font_color": "white",
            "preferred_phase": "99",  # not a real phase
            "csrf_token": token,
        },
    )
    assert response.status_code == 400


def _create_profile_and_get_id(client, token) -> str:
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})
    response = client.get("/profiles")
    import re

    return re.search(rb'/profiles/([a-f0-9]+)/edit', response.data).group(1).decode()


def test_create_and_list_reading_exercise():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    profile_id = _create_profile_and_get_id(client, token)

    token = _get_csrf_token(client)
    client.post(
        f"/profiles/{profile_id}/reading-exercises",
        data={"title": "Homework", "content": "The cat sat.", "csrf_token": token},
    )
    response = client.get(f"/profiles/{profile_id}/reading-exercises")

    assert response.status_code == 200
    assert b"Homework" in response.data
    assert b"Pending" in response.data


def test_reading_exercise_requires_title_and_content():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    profile_id = _create_profile_and_get_id(client, token)

    token = _get_csrf_token(client)
    response = client.post(
        f"/profiles/{profile_id}/reading-exercises",
        data={"title": "", "content": "", "csrf_token": token},
    )
    assert response.status_code == 400


def test_delete_reading_exercise():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    profile_id = _create_profile_and_get_id(client, token)

    token = _get_csrf_token(client)
    client.post(
        f"/profiles/{profile_id}/reading-exercises",
        data={"title": "Homework", "content": "The cat sat.", "csrf_token": token},
    )

    response = client.get(f"/profiles/{profile_id}/reading-exercises")
    import re

    exercise_id = re.search(
        rb'/profiles/[a-f0-9]+/reading-exercises/([a-f0-9]+)/delete', response.data
    ).group(1).decode()

    token = _get_csrf_token(client)
    client.post(
        f"/profiles/{profile_id}/reading-exercises/{exercise_id}/delete",
        data={"csrf_token": token},
    )

    response = client.get(f"/profiles/{profile_id}/reading-exercises")
    assert b"Homework" not in response.data


def test_reading_exercises_are_scoped_per_child():
    app, conn = _make_app()
    client = _authenticated_client(app)
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Anna", "age": "7", "csrf_token": token})
    token = _get_csrf_token(client)
    client.post("/profiles", data={"name": "Ben", "age": "9", "csrf_token": token})

    response = client.get("/profiles")
    import re

    profile_ids = [
        m.decode() for m in re.findall(rb'/profiles/([a-f0-9]+)/edit', response.data)
    ]
    assert len(profile_ids) == 2
    anna_id, ben_id = profile_ids

    token = _get_csrf_token(client)
    client.post(
        f"/profiles/{anna_id}/reading-exercises",
        data={"title": "Anna's homework", "content": "The cat sat.", "csrf_token": token},
    )

    response = client.get(f"/profiles/{ben_id}/reading-exercises")
    assert b"Anna's homework" not in response.data
