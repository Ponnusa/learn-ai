"""
Teacher auth router — applications and invite-code redemption.
Standalone teachers apply here; super_admin approves in admin.py.
"""
import secrets
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from database import get_db
from routers.auth import create_jwt, _user_response
from services.scoring import init_profile

router = APIRouter(prefix="/api/teacher-auth", tags=["teacher-auth"])


# ── Apply as standalone teacher ───────────────────────────────────────────────

class TeacherApplyRequest(BaseModel):
    name:        str
    email:       EmailStr
    school_name: str | None = None
    subject:     str | None = None
    message:     str | None = None


@router.post("/apply")
async def apply_as_teacher(req: TeacherApplyRequest):
    """
    Standalone teacher submits an application.
    Super admin reviews and approves in /admin — this creates a pending row only.
    """
    async with get_db() as db:
        existing = await db.fetchrow(
            "SELECT id, status FROM teacher_applications WHERE email = $1 AND type = 'standalone'",
            req.email,
        )
        if existing:
            if existing["status"] == "pending":
                return {"message": "Application already submitted — we'll be in touch soon."}
            if existing["status"] == "approved":
                return {"message": "Your application was approved — check your email for the invite link."}

        await db.execute("""
            INSERT INTO teacher_applications (type, name, email, school_name, subject, message)
            VALUES ('standalone', $1, $2, $3, $4, $5)
        """, req.name, req.email, req.school_name, req.subject, req.message)

    return {"message": "Application received — we'll review it and be in touch within 24 hours."}


# ── Apply as institution ──────────────────────────────────────────────────────

class InstitutionApplyRequest(BaseModel):
    # Admin contact
    name:         str
    email:        EmailStr
    # Institution details
    school_name:  str
    inst_type:    str        # school | tuition_center | university | coaching
    country:      str | None = None
    email_domain: str | None = None
    est_teachers: int | None = None
    est_students: int | None = None
    message:      str | None = None


@router.post("/apply-institution")
async def apply_as_institution(req: InstitutionApplyRequest):
    """
    Institution admin submits an application.
    Super admin approves → institution + admin user created automatically.
    """
    async with get_db() as db:
        existing = await db.fetchrow(
            "SELECT id, status FROM teacher_applications WHERE email = $1 AND type = 'institution'",
            req.email,
        )
        if existing:
            if existing["status"] == "pending":
                return {"message": "Application already submitted — we'll be in touch soon."}
            if existing["status"] == "approved":
                return {"message": "Your institution is already set up — check your email for login details."}

        await db.execute("""
            INSERT INTO teacher_applications
              (type, name, email, school_name, inst_type, country,
               email_domain, est_teachers, est_students, message)
            VALUES
              ('institution', $1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, req.name, req.email, req.school_name, req.inst_type,
             req.country, req.email_domain, req.est_teachers, req.est_students, req.message)

    return {"message": "Application received — we'll set up your institution within 24 hours."}


# ── Redeem invite code (standalone teacher) ───────────────────────────────────

class RedeemInviteRequest(BaseModel):
    code:  str
    name:  str
    email: EmailStr


@router.post("/redeem-invite")
async def redeem_invite(req: RedeemInviteRequest):
    """
    Teacher redeems a one-time invite code.
    Creates the user account (or upgrades existing) and returns a magic-link token.
    """
    async with get_db() as db:
        invite = await db.fetchrow("""
            SELECT id, email, used_at, expires_at
            FROM teacher_invites
            WHERE code = $1
        """, req.code.upper().strip())

        if not invite:
            raise HTTPException(400, "Invalid invite code")
        if invite["used_at"]:
            raise HTTPException(400, "This invite code has already been used")

        from datetime import datetime
        if datetime.utcnow() > invite["expires_at"].replace(tzinfo=None):
            raise HTTPException(400, "This invite code has expired — please contact us for a new one")

        if invite["email"] and invite["email"].lower() != req.email.lower():
            raise HTTPException(400, "This invite code is assigned to a different email address")

        # Create or upgrade user
        user = await db.fetchrow(
            "SELECT id, email, name, tier, theme, language, account_type FROM users WHERE email = $1",
            req.email,
        )
        if user:
            # Existing user — upgrade to teacher
            await db.execute(
                "UPDATE users SET account_type = 'teacher', name = COALESCE(name, $1), last_seen_at = NOW() WHERE id = $2",
                req.name, user["id"],
            )
            user_id = user["id"]
        else:
            # New user
            user = await db.fetchrow("""
                INSERT INTO users (email, name, account_type, knowledge_level)
                VALUES ($1, $2, 'teacher', 'intermediate')
                RETURNING id, email, name, tier, theme, language, account_type
            """, req.email, req.name)
            await init_profile(str(user["id"]), "intermediate")
            user_id = user["id"]

        # Mark invite as used
        await db.execute("""
            UPDATE teacher_invites SET used_by = $1, used_at = NOW() WHERE id = $2
        """, user_id, invite["id"])

        # Issue a short-lived magic-link token so teacher lands directly in dashboard
        raw_token = secrets.token_urlsafe(32)
        await db.execute("""
            INSERT INTO auth_tokens (user_id, token, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '30 minutes')
        """, user_id, raw_token)

    return {
        "message": "Invite redeemed — check your email to complete sign-in",
        "verify_token": raw_token,   # frontend can auto-verify without extra email step
    }
