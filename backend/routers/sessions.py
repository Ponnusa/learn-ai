"""
Anonymous session management.
Creates a UUID session on first visit, tracked for credit enforcement.
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionCreateRequest(BaseModel):
    session_id: str | None = None   # client can supply existing ID


@router.post("")
async def create_or_get_session(req: SessionCreateRequest, request: Request):
    """
    Called on app load. Returns existing session or creates a new one.
    """
    import hashlib, uuid

    # Hash IP for abuse prevention (never store raw IP)
    ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
    ua = request.headers.get("user-agent", "")
    ua_hash = hashlib.sha256(ua.encode()).hexdigest()[:16]

    async with get_db() as db:
        if req.session_id:
            row = await db.fetchrow(
                "SELECT * FROM anonymous_sessions WHERE id = $1", req.session_id
            )
            if row:
                return _session_response(row)

        # Create new session
        row = await db.fetchrow("""
            INSERT INTO anonymous_sessions (ip_hash, user_agent_hash)
            VALUES ($1, $2) RETURNING *
        """, ip_hash, ua_hash)

    return _session_response(row)


@router.get("/{session_id}/usage")
async def get_session_usage(session_id: str):
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT * FROM anonymous_sessions WHERE id = $1", session_id
        )
    if not row:
        return {"msg_count": 0, "video_count": 0, "quiz_count": 0, "upload_count": 0}
    return {
        "msg_count":    row["msg_count"],
        "video_count":  row["video_count"],
        "quiz_count":   row["quiz_count"],
        "upload_count": row["upload_count"],
        "converted":    row["converted_to"] is not None,
    }


def _session_response(row) -> dict:
    return {
        "session_id":   str(row["id"]),
        "msg_count":    row["msg_count"],
        "video_count":  row["video_count"],
        "quiz_count":   row["quiz_count"],
        "upload_count": row["upload_count"],
        "converted":    row["converted_to"] is not None,
    }
