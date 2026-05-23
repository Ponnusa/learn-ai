"""
Auth router — magic link + JWT session tokens.
"""
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from jose import jwt
from database import get_db
from config import settings
from services.scoring import init_profile

router = APIRouter(prefix="/api/auth", tags=["auth"])


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


class MagicLinkRequest(BaseModel):
    email: EmailStr
    session_id: str | None = None   # merge anonymous session on signup
    knowledge_level: str = "intermediate"


class VerifyTokenRequest(BaseModel):
    token: str


@router.post("/magic-link")
async def send_magic_link(req: MagicLinkRequest):
    async with get_db() as db:
        # Upsert user
        user = await db.fetchrow(
            "SELECT id, tier FROM users WHERE email = $1", req.email
        )
        if not user:
            user = await db.fetchrow("""
                INSERT INTO users (email, knowledge_level)
                VALUES ($1, $2) RETURNING id, tier
            """, req.email, req.knowledge_level)
            await init_profile(str(user["id"]), req.knowledge_level)

        # Create token (expires 15 min)
        raw_token = secrets.token_urlsafe(32)
        await db.execute("""
            INSERT INTO auth_tokens (user_id, token, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '15 minutes')
        """, user["id"], raw_token)

    # Send email via Resend (or just return token in dev)
    magic_url = f"{settings.APP_URL}/auth/verify?token={raw_token}"
    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": req.email,
            "subject": "Your Learn-AI login link",
            "html": f'<a href="{magic_url}">Click here to sign in</a> (expires in 15 min)',
        })
    except Exception:
        pass  # in dev, token is returned below

    return {"message": "Magic link sent", "dev_url": magic_url if settings.APP_URL.startswith("http://localhost") else None}


@router.post("/verify")
async def verify_magic_link(req: VerifyTokenRequest):
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT at.user_id, at.used_at, at.expires_at, u.tier, u.email, u.name
            FROM auth_tokens at
            JOIN users u ON u.id = at.user_id
            WHERE at.token = $1
        """, req.token)

        if not row:
            raise HTTPException(status_code=400, detail="Invalid token")
        if row["used_at"]:
            raise HTTPException(status_code=400, detail="Token already used")
        if datetime.utcnow() > row["expires_at"].replace(tzinfo=None):
            raise HTTPException(status_code=400, detail="Token expired")

        await db.execute(
            "UPDATE auth_tokens SET used_at = NOW() WHERE token = $1", req.token
        )
        await db.execute(
            "UPDATE users SET last_seen_at = NOW() WHERE id = $1", row["user_id"]
        )

    jwt_token = create_jwt(str(row["user_id"]))
    return {
        "token": jwt_token,
        "user": {
            "id": str(row["user_id"]),
            "email": row["email"],
            "name": row["name"],
            "tier": row["tier"],
        }
    }


@router.get("/me")
async def get_me(user_id: str = Depends(lambda: None)):
    # Resolved by the identity dependency in main.py
    pass
