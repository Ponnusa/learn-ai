"""
Super admin router — user management, application review, invite codes, platform stats.
All routes require account_type = 'super_admin'.
"""
import secrets
import string
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from database import get_db
from routers.auth import decode_jwt, _hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _gen_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _require_super_admin(authorization: str = Header(...)):
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT account_type FROM users WHERE id = $1::uuid", user_id
        )
    if not row or row["account_type"] != "super_admin":
        raise HTTPException(403, "Super admin access required")
    return user_id


# ── Platform stats ────────────────────────────────────────────────────────────

@router.get("/stats")
async def platform_stats(authorization: str = Header(...)):
    await _require_super_admin(authorization)
    async with get_db() as db:
        users_total    = await db.fetchval("SELECT COUNT(*) FROM users")
        teachers_total = await db.fetchval("SELECT COUNT(*) FROM users WHERE account_type = 'teacher'")
        active_users   = await db.fetchval("SELECT COUNT(*) FROM users WHERE is_active = true")
        institutions   = await db.fetchval("SELECT COUNT(*) FROM institutions")
        pending_apps   = await db.fetchval("SELECT COUNT(*) FROM teacher_applications WHERE status = 'pending'")
        unused_invites = await db.fetchval("SELECT COUNT(*) FROM teacher_invites WHERE used_at IS NULL AND expires_at > NOW()")
        total_messages = await db.fetchval("SELECT COUNT(*) FROM messages WHERE role = 'user'")
        total_videos   = await db.fetchval("SELECT COUNT(*) FROM videos")

    return {
        "users_total":          int(users_total or 0),
        "users_active":         int(active_users or 0),
        "teachers_total":       int(teachers_total or 0),
        "institutions":         int(institutions or 0),
        "pending_applications": int(pending_apps or 0),
        "unused_invites":       int(unused_invites or 0),
        "total_messages":       int(total_messages or 0),
        "total_videos":         int(total_videos or 0),
    }


# ── User management ───────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    account_type: str | None = Query(None),
    is_active:    bool | None = Query(None),
    search:       str | None  = Query(None),
    limit:        int         = Query(50, le=200),
    offset:       int         = Query(0),
    authorization: str = Header(...),
):
    await _require_super_admin(authorization)

    filters = ["1=1"]
    params: list = []

    if account_type:
        params.append(account_type)
        filters.append(f"u.account_type = ${len(params)}")
    if is_active is not None:
        params.append(is_active)
        filters.append(f"u.is_active = ${len(params)}")
    if search:
        params.append(f"%{search}%")
        filters.append(f"(u.email ILIKE ${len(params)} OR u.name ILIKE ${len(params)})")

    where = " AND ".join(filters)
    params += [limit, offset]

    async with get_db() as db:
        rows = await db.fetch(f"""
            SELECT
                u.id, u.email, u.name, u.account_type, u.tier,
                u.is_active, u.created_at, u.last_seen_at,
                COUNT(DISTINCT m.id)  FILTER (WHERE m.role = 'user') AS msg_count,
                COUNT(DISTINCT v.id)                                   AS video_count
            FROM users u
            LEFT JOIN conversations c  ON c.user_id  = u.id
            LEFT JOIN messages      m  ON m.conversation_id = c.id
            LEFT JOIN videos        v  ON v.user_id  = u.id
            WHERE {where}
            GROUP BY u.id
            ORDER BY u.created_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """, *params)

        total = await db.fetchval(f"""
            SELECT COUNT(*) FROM users u WHERE {where}
        """, *params[:-2])

    return {
        "total": int(total or 0),
        "users": [
            {
                "id":           str(r["id"]),
                "email":        r["email"],
                "name":         r["name"],
                "account_type": r["account_type"],
                "tier":         r["tier"],
                "is_active":    r["is_active"],
                "created_at":   r["created_at"].isoformat(),
                "last_seen_at": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
                "msg_count":    int(r["msg_count"]   or 0),
                "video_count":  int(r["video_count"] or 0),
            }
            for r in rows
        ],
    }


class UpdateUserRequest(BaseModel):
    is_active:    bool | None = None
    account_type: str | None = None
    tier:         str | None = None
    new_password: str | None = None


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    req:     UpdateUserRequest,
    authorization: str = Header(...),
):
    admin_id = await _require_super_admin(authorization)
    if user_id == admin_id:
        raise HTTPException(400, "Cannot modify your own account here")

    if req.new_password is not None and len(req.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    sets, params = [], []

    if req.is_active is not None:
        params.append(req.is_active)
        sets.append(f"is_active = ${len(params)}")
    if req.account_type is not None:
        params.append(req.account_type)
        sets.append(f"account_type = ${len(params)}")
    if req.tier is not None:
        params.append(req.tier)
        sets.append(f"tier = ${len(params)}")
    if req.new_password is not None:
        params.append(_hash_password(req.new_password))
        sets.append(f"password_hash = ${len(params)}")

    if not sets:
        raise HTTPException(400, "Nothing to update")

    params.append(user_id)
    async with get_db() as db:
        await db.execute(
            f"UPDATE users SET {', '.join(sets)} WHERE id = ${len(params)}::uuid",
            *params,
        )

    return {"ok": True}


# ── Applications ──────────────────────────────────────────────────────────────

@router.get("/applications")
async def list_applications(
    status: str = "pending",
    authorization: str = Header(...),
):
    await _require_super_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, type, name, email, school_name, subject, inst_type,
                   country, est_teachers, est_students, email_domain,
                   message, status, created_at
            FROM teacher_applications
            WHERE status = $1
            ORDER BY created_at ASC
        """, status)
    return [
        {
            "id":           str(r["id"]),
            "type":         r["type"],
            "name":         r["name"],
            "email":        r["email"],
            "school_name":  r["school_name"],
            "subject":      r["subject"],
            "inst_type":    r["inst_type"],
            "country":      r["country"],
            "est_teachers": r["est_teachers"],
            "est_students": r["est_students"],
            "email_domain": r["email_domain"],
            "message":      r["message"],
            "status":       r["status"],
            "created_at":   r["created_at"].isoformat(),
        }
        for r in rows
    ]


class ReviewApplicationRequest(BaseModel):
    action:        str
    reject_reason: str | None = None


@router.post("/applications/{application_id}/review")
async def review_application(
    application_id: str,
    req:            ReviewApplicationRequest,
    authorization:  str = Header(...),
):
    if req.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be 'approve' or 'reject'")
    admin_id = await _require_super_admin(authorization)

    async with get_db() as db:
        app = await db.fetchrow(
            "SELECT * FROM teacher_applications WHERE id = $1::uuid", application_id
        )
        if not app:
            raise HTTPException(404, "Application not found")
        if app["status"] != "pending":
            raise HTTPException(400, f"Application is already {app['status']}")

        await db.execute("""
            UPDATE teacher_applications
            SET status = $1, reviewed_by = $2::uuid, reviewed_at = NOW(), reject_reason = $3
            WHERE id = $4::uuid
        """, req.action + "d", admin_id, req.reject_reason, application_id)

        invite_code = None
        temp_password = None

        if req.action == "approve" and app["type"] == "standalone":
            temp_password = _gen_password()
            pwd_hash = _hash_password(temp_password)

            user = await db.fetchrow("SELECT id FROM users WHERE email = $1", app["email"])
            if user:
                await db.execute(
                    "UPDATE users SET account_type = 'teacher', password_hash = $1, is_active = true WHERE id = $2",
                    pwd_hash, user["id"]
                )
                user_id = user["id"]
            else:
                user = await db.fetchrow("""
                    INSERT INTO users (email, name, account_type, knowledge_level, password_hash)
                    VALUES ($1, $2, 'teacher', 'intermediate', $3)
                    RETURNING id
                """, app["email"], app["name"], pwd_hash)
                user_id = user["id"]

            row = await db.fetchrow("""
                INSERT INTO teacher_invites (email, note, created_by)
                VALUES ($1, $2, $3::uuid)
                RETURNING code
            """, app["email"], f"Auto-issued for approved application {application_id}", admin_id)
            invite_code = row["code"]

        elif req.action == "approve" and app["type"] == "institution":
            temp_password = _gen_password()
            pwd_hash = _hash_password(temp_password)

            inst = await db.fetchrow("""
                INSERT INTO institutions (name, type, email_domain, country, plan)
                VALUES ($1, $2, $3, $4, 'trial')
                RETURNING id
            """, app["school_name"], app["inst_type"], app["email_domain"], app["country"])

            user = await db.fetchrow("SELECT id FROM users WHERE email = $1", app["email"])
            if not user:
                user = await db.fetchrow("""
                    INSERT INTO users (email, name, account_type, knowledge_level, password_hash)
                    VALUES ($1, $2, 'institution_admin', 'intermediate', $3) RETURNING id
                """, app["email"], app["name"], pwd_hash)
            else:
                await db.execute(
                    "UPDATE users SET account_type = 'institution_admin', password_hash = $1, is_active = true WHERE id = $2",
                    pwd_hash, user["id"]
                )

            await db.execute("""
                INSERT INTO institution_members (institution_id, user_id, role, status, invited_by)
                VALUES ($1, $2, 'admin', 'active', $3::uuid)
                ON CONFLICT DO NOTHING
            """, inst["id"], user["id"], admin_id)

    result: dict = {"ok": True, "action": req.action}
    if invite_code:
        result["invite_code"] = invite_code
    if temp_password:
        result["temp_password"] = temp_password
        result["email"] = app["email"]
        result["note"] = "Share these credentials with the user. They can change the password from Settings."
    return result


# ── Invite codes ──────────────────────────────────────────────────────────────

class CreateInviteRequest(BaseModel):
    email: str | None = None
    note:  str | None = None


@router.post("/invites")
async def create_invite(req: CreateInviteRequest, authorization: str = Header(...)):
    admin_id = await _require_super_admin(authorization)

    temp_password = None
    user_id = None

    async with get_db() as db:
        # If email provided: create/update user with a temp password right away
        if req.email:
            temp_password = _gen_password()
            pwd_hash = _hash_password(temp_password)

            existing = await db.fetchrow("SELECT id FROM users WHERE email = $1", req.email)
            if existing:
                await db.execute(
                    "UPDATE users SET account_type = 'teacher', password_hash = COALESCE(password_hash, $1), is_active = true WHERE id = $2",
                    pwd_hash, existing["id"]
                )
                user_id = existing["id"]
                # Don't overwrite existing password — only set if they have none
            else:
                new_user = await db.fetchrow("""
                    INSERT INTO users (email, account_type, knowledge_level, password_hash)
                    VALUES ($1, 'teacher', 'intermediate', $2) RETURNING id
                """, req.email, pwd_hash)
                user_id = new_user["id"]

        row = await db.fetchrow("""
            INSERT INTO teacher_invites (email, note, created_by)
            VALUES ($1, $2, $3::uuid)
            RETURNING id, code, expires_at
        """, req.email, req.note, admin_id)

    result = {
        "id":         str(row["id"]),
        "code":       row["code"],
        "expires_at": row["expires_at"].isoformat(),
    }
    if temp_password and req.email:
        result["email"]         = req.email
        result["temp_password"] = temp_password
        result["note"]          = "Account created. Share email + temp password with the teacher. They can change it from Settings."

    return result


@router.get("/invites")
async def list_invites(authorization: str = Header(...)):
    await _require_super_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT ti.id, ti.code, ti.email, ti.note, ti.used_at, ti.expires_at,
                   u.email AS used_by_email
            FROM teacher_invites ti
            LEFT JOIN users u ON u.id = ti.used_by
            ORDER BY ti.created_at DESC
            LIMIT 100
        """)
    return [
        {
            "id":            str(r["id"]),
            "code":          r["code"],
            "email":         r["email"],
            "note":          r["note"],
            "used_at":       r["used_at"].isoformat() if r["used_at"] else None,
            "expires_at":    r["expires_at"].isoformat(),
            "used_by_email": r["used_by_email"],
        }
        for r in rows
    ]


# ── Institutions list ─────────────────────────────────────────────────────────

@router.get("/institutions")
async def list_institutions(authorization: str = Header(...)):
    await _require_super_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT i.id, i.name, i.type, i.plan, i.country,
                   i.max_teachers, i.max_students, i.created_at,
                   COUNT(CASE WHEN im.role = 'teacher' AND im.status = 'active' THEN 1 END) AS teacher_count,
                   COUNT(CASE WHEN im.role = 'student' AND im.status = 'active' THEN 1 END) AS student_count
            FROM institutions i
            LEFT JOIN institution_members im ON im.institution_id = i.id
            GROUP BY i.id
            ORDER BY i.created_at DESC
        """)
    return [
        {
            "id":            str(r["id"]),
            "name":          r["name"],
            "type":          r["type"],
            "plan":          r["plan"],
            "country":       r["country"],
            "max_teachers":  r["max_teachers"],
            "max_students":  r["max_students"],
            "teacher_count": int(r["teacher_count"] or 0),
            "student_count": int(r["student_count"] or 0),
            "created_at":    r["created_at"].isoformat(),
        }
        for r in rows
    ]
