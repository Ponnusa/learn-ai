"""
File upload router.
Currently handles PDF region screenshots captured by the frontend PDF viewer.

R2 storage path layout
──────────────────────
  pdf-regions/{user_id}/{YYYYMMDD_HHMMSS}_{uid8}.png   — authenticated users
  pdf-regions/anon/{session_id}/{YYYYMMDD_HHMMSS}_{uid8}.png — anonymous
  pdf-regions/public/{YYYYMMDD_HHMMSS}_{uid8}.png      — fallback (no id)

Returns: { url, key }
  url — fully-qualified public URL (R2_PUBLIC_URL/key)
  key — object key in the bucket
"""
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.manim import _make_r2_client, R2_BUCKET_NAME, R2_PUBLIC_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_MAX_BYTES     = 10 * 1024 * 1024  # 10 MB


@router.post("")
async def upload_file(
    file:       UploadFile = File(...),
    user_id:    str | None = Form(None),
    session_id: str | None = Form(None),
):
    """Upload a file to R2 and return its public URL."""

    # ── Validate ─────────────────────────────────────────────────────────────
    content_type = file.content_type or "application/octet-stream"
    if content_type not in _ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {content_type}")

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(413, "File too large (max 10 MB)")

    # ── Build R2 key ──────────────────────────────────────────────────────────
    ts  = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    ext = content_type.split("/")[-1].replace("jpeg", "jpg")

    if user_id:
        key = f"pdf-regions/{user_id}/{ts}_{uid}.{ext}"
    elif session_id:
        key = f"pdf-regions/anon/{session_id}/{ts}_{uid}.{ext}"
    else:
        key = f"pdf-regions/public/{ts}_{uid}.{ext}"

    # ── Upload to R2 ─────────────────────────────────────────────────────────
    r2 = _make_r2_client()
    if not r2:
        raise HTTPException(503, "File storage (R2) is not configured on this server")

    try:
        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except Exception as exc:
        logger.exception("R2 upload failed: %s", exc)
        raise HTTPException(502, "Upload to storage failed")

    url = f"{R2_PUBLIC_URL.rstrip('/')}/{key}"
    logger.info("Uploaded %s → %s (%d bytes)", key, url, len(data))
    return {"url": url, "key": key}
