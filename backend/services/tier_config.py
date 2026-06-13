"""
Tier config + feature flags — both read from DB and cached 5 min.
Change limits by updating the tier_config or feature_flags table.
No deploy needed.
"""
import asyncio
import time
from database import get_db

# ── Tier config cache ─────────────────────────────────────────────────────────
_tier_cache: dict = {}
_tier_ts: float = 0.0

async def _refresh_tier_cache():
    global _tier_cache, _tier_ts
    async with get_db() as db:
        rows = await db.fetch("SELECT tier, feature, value_int FROM tier_config")
    _tier_cache = {}
    for r in rows:
        _tier_cache.setdefault(r["tier"], {})[r["feature"]] = r["value_int"]
    _tier_ts = time.monotonic()


_FALLBACK_LIMITS: dict[str, dict[str, int]] = {
    "anonymous": {"messages_total": 8,  "quiz_total": 1,  "videos_total": 1,  "images_total": 1,
                  "quiz_questions_max": 3, "video_max_secs": 60},
    "free":      {"messages_daily": 25, "quiz_daily": 5,  "videos_daily": 3,  "images_daily": 3,
                  "quiz_questions_max": 5, "video_max_secs": 60},
    "learner":   {"messages_daily": 100,"quiz_daily": -1, "videos_daily": 5,  "images_daily": 10,
                  "quiz_questions_max": 10,"video_max_secs": 180},
    "pro":       {"messages_daily": -1, "quiz_daily": -1, "videos_daily": 10, "images_daily": -1,
                  "quiz_questions_max": 15,"video_max_secs": 300},
}


async def get_limit(tier: str, feature: str) -> int:
    """
    Returns the int limit for (tier, feature).
    -1 means unlimited. 0 means not available.
    Falls back to hardcoded defaults if the tier_config table is empty.
    Tier is normalised to lowercase so DB values like 'Pro' match 'pro'.
    """
    tier = (tier or "free").lower()
    if time.monotonic() - _tier_ts > 300:
        await _refresh_tier_cache()
    val = _tier_cache.get(tier, {}).get(feature)
    if val is None:
        val = _FALLBACK_LIMITS.get(tier, {}).get(feature, 0)
    return val


# ── Feature flags cache ───────────────────────────────────────────────────────
_flags_cache: dict = {}
_flags_ts: float = 0.0

async def _refresh_flags_cache():
    global _flags_cache, _flags_ts
    async with get_db() as db:
        rows = await db.fetch("SELECT feature, subject, enabled FROM feature_flags")
    _flags_cache = {}
    for r in rows:
        _flags_cache[(r["feature"], r["subject"])] = r["enabled"]
    _flags_ts = time.monotonic()


async def is_feature_enabled(feature: str, subject: str | None = None) -> bool:
    if time.monotonic() - _flags_ts > 300:
        await _refresh_flags_cache()
    if subject:
        val = _flags_cache.get((feature, subject))
        if val is not None:
            return val
    return _flags_cache.get((feature, None), False)


async def video_supported_for(subject: str | None) -> bool:
    if not subject:
        return False
    return await is_feature_enabled("video_generation", subject)
