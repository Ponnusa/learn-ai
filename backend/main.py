"""
Learn-AI Backend — FastAPI
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_pool, close_pool
from config import settings
from routers import auth, sessions, chat, videos, quizzes, uploads, studysets, images


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    # Auto-migrate new columns (safe to run on every startup)
    import logging
    _log = logging.getLogger("startup")
    from database import get_db
    async with get_db() as db:
        for sql in [
            # ── existing columns ─────────────────────────────────────────────
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT",
            # ── StudySet conversation link ────────────────────────────────────
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS study_set_id UUID REFERENCES study_sets(id) ON DELETE SET NULL",
            # ── StudySets: patch old stub schema from 001_initial.sql ────────
            # study_sets — add columns missing from the 001 stub
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS session_id  UUID",
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS summary     TEXT",
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS status      TEXT NOT NULL DEFAULT 'empty'",
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS updated_at  TIMESTAMPTZ DEFAULT NOW()",
            # study_concepts — old stub used 'title' instead of 'name'
            "ALTER TABLE study_concepts ADD COLUMN IF NOT EXISTS name        TEXT",
            "ALTER TABLE study_concepts ADD COLUMN IF NOT EXISTS definition  TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE study_concepts ADD COLUMN IF NOT EXISTS order_index INT NOT NULL DEFAULT 0",
            # backfill name from title for any old rows
            "UPDATE study_concepts SET name = title WHERE name IS NULL AND title IS NOT NULL",
            # ── Educational Images ────────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS educational_images (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
                session_id   UUID REFERENCES anonymous_sessions(id) ON DELETE SET NULL,
                concept      TEXT NOT NULL,
                domain       TEXT,
                spec         JSONB DEFAULT '{}',
                prompt       TEXT,
                image_url    TEXT,
                status       TEXT NOT NULL DEFAULT 'processing',
                error_msg    TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_edu_img_user ON educational_images(user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_edu_img_sess ON educational_images(session_id, created_at DESC)",
            # ── Educational Images: conversation/study-set linking ────────────
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL",
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS study_set_id    UUID REFERENCES study_sets(id) ON DELETE SET NULL",
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS message_id      TEXT",
            "CREATE INDEX IF NOT EXISTS idx_edu_img_conv ON educational_images(conversation_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_edu_img_ss   ON educational_images(study_set_id, created_at DESC)",
            # ── StudySets: create new tables that didn't exist in 001 ─────────
            """
            CREATE TABLE IF NOT EXISTS study_materials (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                study_set_id UUID NOT NULL REFERENCES study_sets(id) ON DELETE CASCADE,
                filename     TEXT NOT NULL DEFAULT 'upload.pdf',
                file_url     TEXT,
                raw_text     TEXT,
                page_count   INT,
                char_count   INT,
                status       TEXT NOT NULL DEFAULT 'pending',
                error_msg    TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS study_flashcards (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                study_set_id UUID NOT NULL REFERENCES study_sets(id) ON DELETE CASCADE,
                concept_id   UUID REFERENCES study_concepts(id) ON DELETE SET NULL,
                front        TEXT NOT NULL,
                back         TEXT NOT NULL,
                order_index  INT NOT NULL DEFAULT 0,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS study_card_reviews (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                flashcard_id UUID NOT NULL REFERENCES study_flashcards(id) ON DELETE CASCADE,
                rating       INT NOT NULL,
                reviewed_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
        ]:
            try:
                await db.execute(sql)
                _log.info("Migration OK: %s", sql.strip()[:60])
            except Exception as exc:
                _log.error("Migration FAILED: %s — %s", sql.strip()[:60], exc)
    yield
    await close_pool()


app = FastAPI(title="Learn-AI API", version="1.0.0", lifespan=lifespan)

_allowed_origins: list[str] = list({
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "https://learnx-ai.com",
    "https://www.learnx-ai.com",
    "https://learn-ai-ebon.vercel.app",   # Vercel preview
    *[o.strip() for o in settings.EXTRA_ALLOWED_ORIGINS.split(",") if o.strip()],
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(videos.router)
app.include_router(quizzes.router)
app.include_router(uploads.router)
app.include_router(studysets.router)
app.include_router(images.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    """Check DB schema — shows columns on users table and all public tables."""
    from database import get_db
    result: dict = {}
    async with get_db() as db:
        cols = await db.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users'
            ORDER BY ordinal_position
        """)
        result["users_columns"] = [r["column_name"] for r in cols]
        result["has_password_hash"] = "password_hash" in result["users_columns"]
        result["has_google_id"]     = "google_id"     in result["users_columns"]

        tables = await db.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        result["tables"] = [r["table_name"] for r in tables]
        result["has_student_profiles"] = "student_profiles" in result["tables"]

        # Test register INSERT inside a real transaction (rolled back)
        try:
            async with db.transaction():
                await db.execute(
                    "INSERT INTO users (email, password_hash) VALUES ($1, $2)",
                    "__healthcheck__@learnai.internal", "x",
                )
                raise Exception("rollback")   # force rollback
        except Exception as exc:
            rolled_back = str(exc) == "rollback"
            result["register_insert_ok"] = rolled_back
            if not rolled_back:
                result["register_insert_error"] = str(exc)

    return result


@app.get("/health/r2")
async def health_r2():
    """Debug endpoint — tests R2 connectivity and returns the actual error if any."""
    import re
    from config import settings
    from services.manim import _make_r2_client, R2_BUCKET_NAME, R2_PUBLIC_URL

    account_id = settings.R2_ACCOUNT_ID or ""
    result = {
        "R2_ACCOUNT_ID":        account_id[:6] + "…" if account_id else "(not set)",
        "R2_ACCOUNT_ID_valid":  bool(re.fullmatch(r"[a-fA-F0-9]{32}", account_id)),
        "R2_ACCESS_KEY_ID":     (settings.R2_ACCESS_KEY_ID or "")[:6] + "…" if settings.R2_ACCESS_KEY_ID else "(not set)",
        "R2_SECRET_KEY_set":    bool(settings.R2_SECRET_ACCESS_KEY),
        "R2_BUCKET_NAME":       R2_BUCKET_NAME or "(not set)",
        "R2_PUBLIC_URL":        R2_PUBLIC_URL or "(not set)",
        "client_created":       False,
        "put_object_ok":        False,
        "error":                None,
    }

    r2 = _make_r2_client()
    if not r2:
        result["error"] = "Client not created — check R2_ACCOUNT_ID (must be 32 hex chars)"
        return result

    result["client_created"] = True
    try:
        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key="health-check/ping.txt",
            Body=b"ok",
            ContentType="text/plain",
        )
        result["put_object_ok"] = True
    except Exception as exc:
        result["error"] = str(exc)

    return result
