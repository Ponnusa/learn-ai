"""Shared credit / rate-limit checking for all chat endpoints."""
from fastapi import HTTPException
from database import get_db
from services.tier_config import get_limit


async def check_message_credit(user_id: str | None, session_id: str | None) -> None:
    """
    Raises HTTPException(429) if the user/session has hit their message limit.
    For logged-in users also records the usage event.
    """
    async with get_db() as db:
        if user_id:
            user = await db.fetchrow("SELECT tier FROM users WHERE id = $1", user_id)
            tier = user["tier"] if user else "free"
            limit = await get_limit(tier, "messages_daily")
            if limit == -1:
                return
            count = await db.fetchval("""
                SELECT COUNT(*) FROM usage_events
                WHERE user_id = $1 AND event_type = 'message_sent'
                AND created_at > NOW() - INTERVAL '1 day'
            """, user_id)
            if count >= limit:
                raise HTTPException(status_code=429, detail="Daily message limit reached")
            await db.execute("""
                INSERT INTO usage_events (user_id, event_type) VALUES ($1, 'message_sent')
            """, user_id)
        elif session_id:
            row = await db.fetchrow(
                "SELECT msg_count FROM anonymous_sessions WHERE id = $1", session_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            limit = await get_limit("anonymous", "messages_total")
            if row["msg_count"] >= limit:
                raise HTTPException(status_code=429, detail="session_limit_reached")
