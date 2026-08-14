"""
Asset manifest — the only path by which a segment's generated asset (image or
clip) gets a real URL.

PORT NOTE (Sprint 6): the dev-repo version built its own boto3 R2 client from
os.getenv(...) and had no DB, so R2 existence-checks alone were the cache.
worker.py already has a live, working r2_client + R2_BUCKET_NAME (currently
hardcoded literals, not env vars — see worker.py's own module-level
constants) — building a SECOND R2 client here from env vars that are likely
unset would silently produce a broken client. Instead, worker.py calls
configure() once at startup to hand this module its existing r2_client/bucket
name/database_url, and this module falls back to env vars only for
standalone use (e.g. running pipeline modules outside the worker process).

The cache is now backed by the real `generated_assets` Postgres table
(migration 019_video_segments.sql) instead of only a raw R2 existence check —
DB row is checked first (cheap), and only trusted if the R2 object it points
at still actually exists.

AssetRef is guarded so it can only be produced by check_cache()/register_asset()
below, both of which perform (or confirm) a real R2 upload first. This is the
structural enforcement of the "no invented URLs" rule: an LLM's text output
can be a string, but it cannot be an AssetRef, because AssetRef.__post_init__
rejects any instance not carrying this module's private sentinel object.
"""
import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import boto3
import psycopg2
from botocore.config import Config

logger = logging.getLogger(__name__)

_CONTENT_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".mp4": "video/mp4", ".svg": "image/svg+xml",
}

_r2_client = None
_r2_bucket_name: Optional[str] = None
_database_url: Optional[str] = None


def configure(r2_client=None, bucket_name: Optional[str] = None, database_url: Optional[str] = None) -> None:
    """Called once by worker.py at startup with its OWN existing r2_client/
    bucket/DB connection string, so this module never builds a second,
    possibly-misconfigured R2 client or looks for a DATABASE_URL env var that
    may not exist under that name in this process."""
    global _r2_client, _r2_bucket_name, _database_url
    if r2_client is not None:
        _r2_client = r2_client
    if bucket_name is not None:
        _r2_bucket_name = bucket_name
    if database_url is not None:
        _database_url = database_url


def _get_r2_client():
    global _r2_client
    if _r2_client is None:
        # Standalone fallback (not the worker's normal path) — env-var based,
        # matching the dev-repo version's construction.
        account_id = os.getenv("R2_ACCOUNT_ID")
        _r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _r2_client


def _get_bucket_name() -> str:
    return _r2_bucket_name or os.getenv("R2_BUCKET_NAME", "learnai-videos")


def _get_database_url() -> str:
    database_url = _database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "asset_manifest has no database configured — call configure(database_url=...) "
            "or set DATABASE_URL"
        )
    return database_url


def _r2_object_exists(key: str) -> bool:
    try:
        _get_r2_client().head_object(Bucket=_get_bucket_name(), Key=key)
        return True
    except Exception:
        return False


def _presigned_url(key: str, expires: int = 3600) -> str:
    return _get_r2_client().generate_presigned_url(
        "get_object", Params={"Bucket": _get_bucket_name(), "Key": key}, ExpiresIn=expires,
    )


def compute_prompt_hash(generation_prompt: str, style_reference: str = "", subject_area: str = "") -> str:
    """Cache key for a generated asset — identical inputs should hit the same R2 object."""
    raw = f"{subject_area}|{style_reference}|{generation_prompt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _db_get_asset(prompt_hash: str) -> Optional[dict]:
    conn = psycopg2.connect(_get_database_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT asset_type, r2_key FROM generated_assets WHERE prompt_hash = %s", (prompt_hash,)
        )
        row = cur.fetchone()
        return {"asset_type": row[0], "r2_key": row[1]} if row else None
    finally:
        conn.close()


def _db_upsert_asset(prompt_hash: str, asset_type: str, r2_key: str) -> None:
    conn = psycopg2.connect(_get_database_url())
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO generated_assets (prompt_hash, asset_type, r2_key)
               VALUES (%s, %s, %s)
               ON CONFLICT (prompt_hash) DO UPDATE
                 SET asset_type = EXCLUDED.asset_type, r2_key = EXCLUDED.r2_key""",
            (prompt_hash, asset_type, r2_key),
        )
        conn.commit()
    finally:
        conn.close()


# Only this module holds this object — no other code can pass the identity
# check in AssetRef.__post_init__, so no other code can construct one.
_AUTHORIZED = object()


@dataclass(frozen=True)
class AssetRef:
    segment_id: str
    asset_type: str    # "image" | "image_clip" | "video_clip" | "held_frame_clip" | "manim_clip"
    r2_key: str
    url: str
    prompt_hash: str
    _authorized: object = field(repr=False, compare=False)

    def __post_init__(self):
        if self._authorized is not _AUTHORIZED:
            raise RuntimeError(
                "AssetRef must come from asset_manifest.register_asset() or check_cache() "
                "— direct construction is not allowed (no-invented-urls rule)."
            )


def check_cache(prompt_hash: str, asset_type: str, segment_id: str, ext: str) -> Optional[AssetRef]:
    """Cache-hit lookup: DB row first (cheap), then confirm the R2 object it
    points at still actually exists before trusting it. Returns None on a
    miss — callers must then generate and call register_asset(), never
    fabricate a URL themselves."""
    row = _db_get_asset(prompt_hash)
    if row is None:
        return None
    if row["asset_type"] != asset_type:
        # Same content hash, different asset type — e.g. a video segment that
        # previously demoted to image (cached as "image_clip") now being
        # looked up as "video_clip". NOT a valid hit for the type requested.
        return None
    r2_key = row["r2_key"]
    if not _r2_object_exists(r2_key):
        logger.warning(f"[asset_manifest] DB row for {prompt_hash} points at a missing R2 object — treating as a miss")
        return None
    return AssetRef(
        segment_id=segment_id, asset_type=row["asset_type"], r2_key=r2_key,
        url=_presigned_url(r2_key), prompt_hash=prompt_hash, _authorized=_AUTHORIZED,
    )


_manim_failures_table_ready = False


def log_manim_failure(video_id: int, segment_order: int, segment_id: str, error: str, code: str) -> None:
    """Persist a Manim render failure so bulk-render dashboards can surface it later."""
    global _manim_failures_table_ready
    conn = psycopg2.connect(_get_database_url())
    try:
        cur = conn.cursor()
        if not _manim_failures_table_ready:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS manim_render_failures (
                    id            SERIAL PRIMARY KEY,
                    video_id      INTEGER,
                    segment_order INTEGER NOT NULL,
                    segment_id    TEXT,
                    error_message TEXT,
                    generated_code TEXT,
                    created_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()
            _manim_failures_table_ready = True
        cur.execute(
            """INSERT INTO manim_render_failures
               (video_id, segment_order, segment_id, error_message, generated_code)
               VALUES (%s, %s, %s, %s, %s)""",
            (video_id, segment_order, segment_id, error[:4000], code),
        )
        conn.commit()
    except Exception as exc:
        logger.warning(f"[asset_manifest] failed to log manim failure: {exc}")
    finally:
        conn.close()


def register_asset(local_path: str, segment_id: str, asset_type: str, prompt_hash: str) -> AssetRef:
    """Upload a locally-generated file to R2 at a deterministic, content-addressed
    key, record it in generated_assets, and return the only valid AssetRef for it."""
    ext = os.path.splitext(local_path)[1] or ".bin"
    r2_key = f"pipeline_assets/{asset_type}/{prompt_hash}{ext}"
    content_type = _CONTENT_TYPES.get(ext.lower(), "application/octet-stream")
    with open(local_path, "rb") as f:
        _get_r2_client().upload_fileobj(
            f, _get_bucket_name(), r2_key, ExtraArgs={"ContentType": content_type},
        )
    _db_upsert_asset(prompt_hash, asset_type, r2_key)
    return AssetRef(
        segment_id=segment_id, asset_type=asset_type, r2_key=r2_key,
        url=_presigned_url(r2_key), prompt_hash=prompt_hash, _authorized=_AUTHORIZED,
    )
