"""
Developer API platform — powers the standalone video-api/ app (separate
Vercel deployment). Two distinct auth models live in this one file:

  - /api/developer/*   session-auth (JWT) — used by the video-api app's own
                       UI: sign up (email/password + company name/description,
                       collected together at signup — see developer_signup()),
                       log in (reuses the main app's existing
                       POST /api/auth/login/password unchanged), check key
                       status, list/generate videos as the logged-in developer.
  - /api/public/v1/*   API-key auth (Bearer <raw key>, hashed and looked up
                       in api_keys) — the actual public contract third-party
                       integrators call from their own code. Kept in a
                       separate, versioned namespace so it can stay stable
                       even as the internal app's routes change.

A key exists the moment it's created (at signup) but is unusable (every check
below rejects it) until a superadmin flips it to 'approved' — see admin.py's
_require_super_admin, reused here rather than a second admin auth system.
That approval step is the real trust boundary for this product, not account
creation — signup deliberately has no email-ownership verification step
(no magic link), since a human reviews the company name/description before
any key actually works either way.

Video generation itself is NOT reimplemented here — both paths below reuse
routers.videos._generate_video_bg, the exact same background pipeline the
main app's own /api/videos/generate uses (Phase 1 GPT solution -> Phase 1.5
flags use_storyboard=TRUE and triggers the GCP worker, which generates the
storyboard itself). This is deliberately the multi-modal path only.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, EmailStr

from database import get_db
from services.tier_config import get_limit
from services.scoring import init_profile
from routers.auth import decode_jwt, _hash_password, create_jwt, _user_response
from routers.admin import _require_super_admin
from routers.videos import _generate_video_bg

logger = logging.getLogger(__name__)

developer_router = APIRouter(prefix="/api/developer", tags=["developer-platform"])
public_router = APIRouter(prefix="/api/public/v1", tags=["public-api"])
admin_dev_router = APIRouter(prefix="/api/admin", tags=["developer-platform-admin"])

_KEY_PREFIX = "lx_live_"
_API_TIER = "api_partner"


# ── Shared helpers ───────────────────────────────────────────────────────────

def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _generate_raw_key() -> str:
    return f"{_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def _mask_key(raw_key: str | None, label_hint: str = "") -> str:
    """Best-effort masked display — raw key is never stored, so this is only
    ever used right after generation, in the same response as the raw key."""
    if not raw_key:
        return ""
    return f"{raw_key[:len(_KEY_PREFIX) + 4]}{'•' * 20}{raw_key[-4:]}"


async def _require_session_user(authorization: str = Header(...)) -> str:
    """Session auth for the video-api app's own UI — same JWT as the main app."""
    return decode_jwt(authorization.removeprefix("Bearer ").strip())


async def _require_api_key(authorization: str = Header(...)) -> dict:
    """
    API-key auth for third-party callers. Returns the api_keys row (as a
    dict) for the caller — includes user_id, status, id. Rejects anything
    but an approved key so a pending/revoked key fails closed, not open.
    """
    raw_key = authorization.removeprefix("Bearer ").strip()
    if not raw_key:
        raise HTTPException(401, "Missing API key")
    key_hash = _hash_key(raw_key)
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT id, user_id, status FROM api_keys WHERE key_hash = $1", key_hash
        )
    if not row:
        raise HTTPException(401, "Invalid API key")
    if row["status"] != "approved":
        raise HTTPException(403, f"API key is {row['status']}, not approved")
    return dict(row)


async def _count_api_videos(api_key_id) -> int:
    async with get_db() as db:
        return await db.fetchval(
            "SELECT COUNT(*) FROM videos WHERE api_key_id = $1", api_key_id
        ) or 0


# ═════════════════════════════════════════════════════════════════════════════
# /api/developer/*  — session-auth, the video-api app's own UI
# ═════════════════════════════════════════════════════════════════════════════

class DeveloperSignupBody(BaseModel):
    email: EmailStr
    password: str
    company_name: str
    description: str  # what they intend to build — shown to the approver


@developer_router.post("/signup")
async def developer_signup(body: DeveloperSignupBody):
    """
    Creates the account AND the pending key request in one call — company
    name/description are collected at signup instead of as a separate
    dashboard step. Mirrors routers.auth.register()'s validation exactly
    (same password rule, same duplicate-email check, same hashing) since
    this creates a row in the same users table; login reuses
    POST /api/auth/login/password unchanged, no new login endpoint needed.
    """
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    hashed = _hash_password(body.password)

    async with get_db() as db:
        existing = await db.fetchrow("SELECT id FROM users WHERE email = $1", body.email)
        if existing:
            raise HTTPException(409, "An account with this email already exists")
        user = await db.fetchrow("""
            INSERT INTO users (email, password_hash, account_type)
            VALUES ($1, $2, 'api_developer')
            RETURNING id, email, name, tier, theme, language, account_type
        """, body.email, hashed)

    try:
        await init_profile(str(user["id"]), "intermediate")
    except Exception as exc:
        logger.warning("init_profile failed for developer signup %s (non-fatal): %s", user["id"], exc)

    raw_key = _generate_raw_key()
    key_hash = _hash_key(raw_key)
    async with get_db() as db:
        key_row = await db.fetchrow("""
            INSERT INTO api_keys (user_id, key_hash, company_name, description, status)
            VALUES ($1::uuid, $2, $3, $4, 'pending')
            RETURNING id, status, created_at
        """, user["id"], key_hash, body.company_name.strip()[:200], body.description.strip()[:2000])

    resp = _user_response(user, create_jwt(str(user["id"])))
    resp["api_key"] = {
        "id": str(key_row["id"]),
        "status": key_row["status"],
        "created_at": key_row["created_at"],
        "api_key": raw_key,   # shown ONCE — never retrievable again after this response
        "masked": _mask_key(raw_key),
    }
    return resp


class RequestKeyBody(BaseModel):
    company_name: str
    description: str


@developer_router.post("/api-key/request")
async def request_api_key(body: RequestKeyBody, authorization: str = Header(...)):
    """Follow-up path only (e.g. a revoked key needing a fresh request) —
    signup already creates the first key, so this is not the common case."""
    caller_id = await _require_session_user(authorization)
    async with get_db() as db:
        existing = await db.fetchrow(
            "SELECT id, status FROM api_keys WHERE user_id = $1::uuid ORDER BY created_at DESC LIMIT 1",
            caller_id,
        )
        if existing and existing["status"] in ("pending", "approved"):
            raise HTTPException(400, f"You already have a key ({existing['status']}) — revoke it first to request a new one")

        raw_key = _generate_raw_key()
        key_hash = _hash_key(raw_key)
        row = await db.fetchrow("""
            INSERT INTO api_keys (user_id, key_hash, company_name, description, status)
            VALUES ($1::uuid, $2, $3, $4, 'pending')
            RETURNING id, status, created_at
        """, caller_id, key_hash, body.company_name.strip()[:200], body.description.strip()[:2000])

    return {
        "id": str(row["id"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "api_key": raw_key,   # shown ONCE — never retrievable again after this response
        "masked": _mask_key(raw_key),
    }


@developer_router.get("/api-key")
async def get_my_api_key(authorization: str = Header(...)):
    caller_id = await _require_session_user(authorization)
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT id, status, company_name, description, created_at, approved_at, revoked_at FROM api_keys "
            "WHERE user_id = $1::uuid ORDER BY created_at DESC LIMIT 1",
            caller_id,
        )
    if not row:
        return {"has_key": False}
    return {"has_key": True, **dict(row), "id": str(row["id"])}


@developer_router.post("/api-key/regenerate")
async def regenerate_api_key(authorization: str = Header(...)):
    """
    Rotates the key material on the caller's current pending/approved key
    WITHOUT touching its status or approved_at — the raw key is only ever
    shown once (at signup or here), so this is the only way to recover from
    "I didn't copy it down." An approved key stays approved and is usable
    with the new value immediately; no re-review needed, since the thing a
    superadmin vets is the company/use-case, not any one key value. The old
    raw key stops working the instant this runs (its hash is overwritten).

    Deliberately does NOT work on a revoked key — that's a superadmin trust
    decision, not something self-service should be able to route around;
    use POST /api-key/request for a fresh (re-reviewed) key in that case.
    """
    caller_id = await _require_session_user(authorization)
    raw_key = _generate_raw_key()
    key_hash = _hash_key(raw_key)
    async with get_db() as db:
        row = await db.fetchrow("""
            UPDATE api_keys SET key_hash = $1
            WHERE id = (
                SELECT id FROM api_keys
                WHERE user_id = $2::uuid AND status IN ('pending', 'approved')
                ORDER BY created_at DESC LIMIT 1
            )
            RETURNING id, status, created_at
        """, key_hash, caller_id)
    if not row:
        raise HTTPException(404, "No active key to regenerate — request one first")
    return {
        "id": str(row["id"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "api_key": raw_key,   # shown ONCE — never retrievable again after this response
        "masked": _mask_key(raw_key),
    }


@developer_router.get("/videos")
async def list_my_videos(authorization: str = Header(...)):
    caller_id = await _require_session_user(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, status, video_url, thumbnail_url, prompt, subject, language,
                   duration_secs, created_at, error_message
            FROM videos
            WHERE user_id = $1::uuid AND source = 'external_api'
            ORDER BY created_at DESC
        """, caller_id)
    return [dict(r) for r in rows]


class GenerateBody(BaseModel):
    topic: str
    subject: str | None = None
    language: str = "en"
    aspect_ratio: str = "16:9"


# Deliberately narrow for now — matches the video-api UI's generate form.
# The public API bypasses that form entirely (curl/Python/etc. callers), and
# with only one lifetime video per account during the beta, an unsupported
# subject/aspect_ratio should reject clearly rather than silently produce
# something broken or unconfirmed with a developer's one shot.
_ALLOWED_SUBJECTS = {"physics", "chemistry", "mathematics"}
_ALLOWED_ASPECT_RATIOS = {"16:9"}


async def _start_generation(user_id: str, api_key_id, body: GenerateBody, bg: BackgroundTasks) -> dict:
    """Shared by both the session-auth UI endpoint and the public API endpoint
    below — same quota check, same video row shape, same background pipeline."""
    if body.subject not in _ALLOWED_SUBJECTS:
        raise HTTPException(400, f"subject must be one of: {', '.join(sorted(_ALLOWED_SUBJECTS))}")
    if body.aspect_ratio not in _ALLOWED_ASPECT_RATIOS:
        raise HTTPException(
            400,
            f"aspect_ratio must be one of: {', '.join(sorted(_ALLOWED_ASPECT_RATIOS))} "
            "(others aren't confirmed to render correctly yet)",
        )

    limit = await get_limit(_API_TIER, "videos_lifetime")
    if limit >= 0:
        used = await _count_api_videos(api_key_id)
        if used >= limit:
            raise HTTPException(429, f"Lifetime limit reached ({limit} video{'s' if limit != 1 else ''} per account)")

    max_secs = await get_limit(_API_TIER, "video_max_secs") or 60

    async with get_db() as db:
        video = await db.fetchrow("""
            INSERT INTO videos
              (user_id, prompt, status, max_duration, language, aspect_ratio, subject,
               quality_tier, source, api_key_id)
            VALUES ($1::uuid, $2, 'pending', $3, $4, $5, $6, 'standard', 'external_api', $7)
            RETURNING id
        """, user_id, body.topic, max_secs, body.language, body.aspect_ratio, body.subject, api_key_id)

    video_id = video["id"]
    bg.add_task(
        _generate_video_bg,
        video_id, body.topic, user_id, body.subject, body.language, body.aspect_ratio,
        max_secs, None, "standard",
    )
    return {"video_id": video_id, "status": "pending"}


@developer_router.post("/videos/generate")
async def generate_video_from_ui(body: GenerateBody, bg: BackgroundTasks, authorization: str = Header(...)):
    caller_id = await _require_session_user(authorization)
    async with get_db() as db:
        key_row = await db.fetchrow(
            "SELECT id FROM api_keys WHERE user_id = $1::uuid AND status = 'approved' LIMIT 1",
            caller_id,
        )
    if not key_row:
        raise HTTPException(403, "No approved API key on this account yet")
    return await _start_generation(caller_id, key_row["id"], body, bg)


# ═════════════════════════════════════════════════════════════════════════════
# /api/admin/developer-keys  — superadmin approve/revoke, reuses admin auth
# ═════════════════════════════════════════════════════════════════════════════

@admin_dev_router.get("/developer-keys")
async def list_developer_keys(authorization: str = Header(...)):
    await _require_super_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT k.id, k.status, k.company_name, k.description, k.created_at, k.approved_at, k.revoked_at,
                   u.email, u.name,
                   (SELECT COUNT(*) FROM videos v WHERE v.api_key_id = k.id) AS videos_generated
            FROM api_keys k
            JOIN users u ON u.id = k.user_id
            ORDER BY k.created_at DESC
        """)
    return [dict(r) | {"id": str(r["id"])} for r in rows]


@admin_dev_router.post("/developer-keys/{key_id}/approve")
async def approve_developer_key(key_id: str, authorization: str = Header(...)):
    await _require_super_admin(authorization)
    async with get_db() as db:
        row = await db.fetchrow(
            "UPDATE api_keys SET status = 'approved', approved_at = NOW() "
            "WHERE id = $1::uuid RETURNING id, status",
            key_id,
        )
    if not row:
        raise HTTPException(404, "Key not found")
    return {"id": str(row["id"]), "status": row["status"]}


@admin_dev_router.post("/developer-keys/{key_id}/revoke")
async def revoke_developer_key(key_id: str, authorization: str = Header(...)):
    await _require_super_admin(authorization)
    async with get_db() as db:
        row = await db.fetchrow(
            "UPDATE api_keys SET status = 'revoked', revoked_at = NOW() "
            "WHERE id = $1::uuid RETURNING id, status",
            key_id,
        )
    if not row:
        raise HTTPException(404, "Key not found")
    return {"id": str(row["id"]), "status": row["status"]}


# ═════════════════════════════════════════════════════════════════════════════
# /api/public/v1/*  — API-key auth, the actual public contract
# ═════════════════════════════════════════════════════════════════════════════

@public_router.post("/videos/generate")
async def public_generate_video(body: GenerateBody, bg: BackgroundTasks, authorization: str = Header(...)):
    key = await _require_api_key(authorization)
    return await _start_generation(str(key["user_id"]), key["id"], body, bg)


@public_router.get("/videos/{video_id}")
async def public_get_video(video_id: int, authorization: str = Header(...)):
    key = await _require_api_key(authorization)
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT id, status, video_url, thumbnail_url, error_message,
                   duration_secs, prompt, subject, language, created_at, api_key_id
            FROM videos WHERE id = $1
        """, video_id)
    if not row or row["api_key_id"] != key["id"]:
        raise HTTPException(404, "Video not found")
    return dict(row)


@public_router.get("/videos")
async def public_list_videos(authorization: str = Header(...)):
    key = await _require_api_key(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, status, video_url, thumbnail_url, prompt, subject, language,
                   duration_secs, created_at, error_message
            FROM videos WHERE api_key_id = $1
            ORDER BY created_at DESC
        """, key["id"])
    return [dict(r) for r in rows]
