"""
Auth router — magic link + email/password + Google OAuth.
All methods return the same { token, user } shape so the frontend
can treat them identically.
"""
import secrets
import urllib.parse
from datetime import datetime, timedelta

import bcrypt
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from jose import jwt

from database import get_db
from config import settings
from services.scoring import init_profile

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_jwt(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _user_response(row, jwt_token: str) -> dict:
    return {
        "token": jwt_token,
        "user": {
            "id":    str(row["id"]),
            "email": row["email"],
            "name":  row["name"],
            "tier":  row["tier"],
        },
    }


# ── Magic link ────────────────────────────────────────────────────────────────

class MagicLinkRequest(BaseModel):
    email: EmailStr
    session_id: str | None = None
    knowledge_level: str = "intermediate"


class VerifyTokenRequest(BaseModel):
    token: str


@router.post("/magic-link")
async def send_magic_link(req: MagicLinkRequest):
    async with get_db() as db:
        user = await db.fetchrow("SELECT id, tier FROM users WHERE email = $1", req.email)
        if not user:
            user = await db.fetchrow("""
                INSERT INTO users (email, knowledge_level)
                VALUES ($1, $2) RETURNING id, tier
            """, req.email, req.knowledge_level)
            await init_profile(str(user["id"]), req.knowledge_level)

        raw_token = secrets.token_urlsafe(32)
        await db.execute("""
            INSERT INTO auth_tokens (user_id, token, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '15 minutes')
        """, user["id"], raw_token)

    magic_url = f"{settings.APP_URL}/auth/verify?token={raw_token}"
    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from":    settings.FROM_EMAIL,
            "to":      req.email,
            "subject": "Your Learn-AI sign-in link",
            "html": f"""
                <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px">
                  <h2 style="color:#7c3aed">LearnX-AI</h2>
                  <p>Click the button below to sign in. This link expires in 15 minutes.</p>
                  <a href="{magic_url}"
                     style="display:inline-block;padding:12px 28px;background:#7c3aed;
                            color:#fff;border-radius:8px;text-decoration:none;font-weight:600">
                    Sign in to LearnX-AI
                  </a>
                  <p style="color:#888;font-size:12px;margin-top:24px">
                    If you didn't request this, you can safely ignore this email.
                  </p>
                </div>
            """,
        })
    except Exception:
        pass  # In dev the URL is returned below

    return {
        "message": "Magic link sent — check your email",
        "dev_url": magic_url if settings.APP_URL.startswith("http://localhost") else None,
    }


@router.post("/verify")
async def verify_magic_link(req: VerifyTokenRequest):
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT at.user_id, at.used_at, at.expires_at, u.tier, u.email, u.name, u.id
            FROM auth_tokens at
            JOIN users u ON u.id = at.user_id
            WHERE at.token = $1
        """, req.token)

        if not row:
            raise HTTPException(400, "Invalid link")
        if row["used_at"]:
            raise HTTPException(400, "This link has already been used")
        if datetime.utcnow() > row["expires_at"].replace(tzinfo=None):
            raise HTTPException(400, "This link has expired — please request a new one")

        await db.execute("UPDATE auth_tokens SET used_at = NOW() WHERE token = $1", req.token)
        await db.execute("UPDATE users SET last_seen_at = NOW() WHERE id = $1", row["user_id"])

    return _user_response(row, create_jwt(str(row["user_id"])))


# ── Email / password ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None
    session_id: str | None = None
    knowledge_level: str = "intermediate"


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(req: RegisterRequest):
    import logging
    log = logging.getLogger(__name__)

    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    hashed = _hash_password(req.password)

    # ── 1. Create user row ────────────────────────────────────────────────────
    async with get_db() as db:
        existing = await db.fetchrow("SELECT id FROM users WHERE email = $1", req.email)
        if existing:
            raise HTTPException(409, "An account with this email already exists")

        try:
            user = await db.fetchrow("""
                INSERT INTO users (email, name, password_hash, knowledge_level)
                VALUES ($1, $2, $3, $4) RETURNING id, email, name, tier
            """, req.email, req.name, hashed, req.knowledge_level)
        except Exception as exc:
            log.exception("register INSERT failed: %s", exc)
            raise HTTPException(500, f"Registration failed: {exc}")

    # ── 2. Init skill profile (separate connection, non-fatal if it fails) ────
    try:
        await init_profile(str(user["id"]), req.knowledge_level)
    except Exception as exc:
        log.warning("init_profile failed for %s (non-fatal): %s", user["id"], exc)

    return _user_response(user, create_jwt(str(user["id"])))


@router.post("/login/password")
async def login_password(req: PasswordLoginRequest):
    async with get_db() as db:
        user = await db.fetchrow(
            "SELECT id, email, name, tier, password_hash FROM users WHERE email = $1", req.email
        )

    if not user or not user["password_hash"]:
        raise HTTPException(401, "Invalid email or password")
    if not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    async with get_db() as db:
        await db.execute("UPDATE users SET last_seen_at = NOW() WHERE id = $1", user["id"])

    return _user_response(user, create_jwt(str(user["id"])))


# ── Google OAuth ──────────────────────────────────────────────────────────────

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL  = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES    = "openid email profile"


@router.get("/google")
async def google_auth_redirect():
    """Return the Google OAuth authorization URL."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google login is not configured on this server")

    redirect_uri = f"{settings.APP_URL}/auth/callback"
    state = secrets.token_urlsafe(16)

    params = urllib.parse.urlencode({
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         GOOGLE_SCOPES,
        "state":         state,
        "access_type":   "online",
        "prompt":        "select_account",
    })
    return {"url": f"{GOOGLE_AUTH_URL}?{params}", "state": state}


class GoogleCallbackRequest(BaseModel):
    code: str
    session_id: str | None = None


@router.post("/google/callback")
async def google_callback(req: GoogleCallbackRequest):
    """Exchange Google auth code for user info, create/update user, return JWT."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google login is not configured on this server")

    redirect_uri = f"{settings.APP_URL}/auth/callback"

    async with httpx.AsyncClient(timeout=10) as client:
        # Exchange code → access token
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          req.code,
            "client_id":     settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(400, "Failed to exchange Google auth code")

        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        if not access_token:
            raise HTTPException(400, "No access token from Google")

        # Fetch user profile
        user_resp = await client.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(400, "Failed to fetch Google user info")

        g = user_resp.json()

    google_id = g.get("id")
    email     = g.get("email")
    name      = g.get("name")

    if not email:
        raise HTTPException(400, "Google account has no email address")

    async with get_db() as db:
        # Try to find by google_id first, then by email
        user = await db.fetchrow(
            "SELECT id, email, name, tier FROM users WHERE google_id = $1", google_id
        )
        if not user:
            user = await db.fetchrow(
                "SELECT id, email, name, tier FROM users WHERE email = $1", email
            )

        if user:
            # Update google_id + last_seen
            await db.execute("""
                UPDATE users SET google_id = $1, last_seen_at = NOW(),
                    name = COALESCE(name, $2) WHERE id = $3
            """, google_id, name, user["id"])
        else:
            # New user via Google
            user = await db.fetchrow("""
                INSERT INTO users (email, name, google_id, knowledge_level)
                VALUES ($1, $2, $3, 'intermediate') RETURNING id, email, name, tier
            """, email, name, google_id)
            await init_profile(str(user["id"]), "intermediate")

    return _user_response(user, create_jwt(str(user["id"])))


# ── /me ───────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me():
    pass  # Resolved by identity dependency in main.py


# ── /stats ────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_user_stats(user_id: str):
    """
    Returns real lifetime stats for a logged-in user, pulled from the DB.
    Queried fresh on every page load — never cached in the session store.
    """
    async with get_db() as db:
        # Messages sent (user-role messages in their conversations)
        messages = await db.fetchval("""
            SELECT COUNT(*) FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.user_id = $1::uuid AND m.role = 'user'
        """, user_id) or 0

        # Completed videos
        videos = await db.fetchval("""
            SELECT COUNT(*) FROM videos
            WHERE user_id = $1::uuid AND status IN ('complete', 'completed')
        """, user_id) or 0

        # Quizzes completed (submitted)
        quizzes = await db.fetchval("""
            SELECT COUNT(*) FROM quizzes
            WHERE user_id = $1::uuid AND completed_at IS NOT NULL
        """, user_id) or 0

        # Conversations started
        conversations = await db.fetchval("""
            SELECT COUNT(*) FROM conversations WHERE user_id = $1::uuid
        """, user_id) or 0

        # Most studied subject
        top_subject_row = await db.fetchrow("""
            SELECT subject, COUNT(*) AS cnt
            FROM conversations
            WHERE user_id = $1::uuid AND subject IS NOT NULL
            GROUP BY subject ORDER BY cnt DESC LIMIT 1
        """, user_id)

        # Account creation date
        user_row = await db.fetchrow(
            "SELECT created_at FROM users WHERE id = $1::uuid", user_id
        )

    return {
        "messages":      int(messages),
        "videos":        int(videos),
        "quizzes":       int(quizzes),
        "conversations": int(conversations),
        "top_subject":   top_subject_row["subject"] if top_subject_row else None,
        "member_since":  user_row["created_at"].isoformat() if user_row else None,
    }
