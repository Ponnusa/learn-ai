"""
Learn-AI Backend — FastAPI
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_pool, close_pool
from config import settings
from routers import auth, sessions, chat, videos, quizzes, uploads


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    # Auto-migrate new columns (safe to run on every startup)
    import logging
    _log = logging.getLogger("startup")
    from database import get_db
    async with get_db() as db:
        for sql in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT",
        ]:
            try:
                await db.execute(sql)
                _log.info("Migration OK: %s", sql[:60])
            except Exception as exc:
                _log.error("Migration FAILED: %s — %s", sql[:60], exc)
    yield
    await close_pool()


app = FastAPI(title="Learn-AI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
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
