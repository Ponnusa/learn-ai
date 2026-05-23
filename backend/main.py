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
