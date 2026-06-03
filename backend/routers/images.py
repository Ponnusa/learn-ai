"""
Educational Image Generator API

  POST /api/images/generate        — start a generation job (async)
  GET  /api/images/{job_id}        — poll job status / retrieve result
  GET  /api/images                 — list user's past images
"""
import uuid
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["images"])


class GenerateRequest(BaseModel):
    concept:    str
    user_id:    str | None = None
    session_id: str | None = None


@router.post("/generate")
async def generate_image(req: GenerateRequest, bg: BackgroundTasks):
    concept = req.concept.strip()
    if not concept:
        raise HTTPException(400, "concept is required")
    if len(concept) > 500:
        raise HTTPException(400, "concept must be 500 characters or fewer")

    job_id = str(uuid.uuid4())

    async with get_db() as db:
        await db.execute(
            """INSERT INTO educational_images (id, user_id, session_id, concept, status)
               VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'processing')""",
            job_id, req.user_id, req.session_id, concept,
        )

    from services.educational_image import process_image_job
    bg.add_task(process_image_job, job_id, concept, req.user_id, req.session_id)

    logger.info("[edu-img] job created: %s", job_id[:8])
    return {"jobId": job_id, "status": "processing"}


@router.get("/{job_id}")
async def get_image_job(job_id: str):
    async with get_db() as db:
        row = await db.fetchrow(
            """SELECT id, concept, domain, spec, prompt, image_url, status, error_msg, created_at
               FROM educational_images WHERE id = $1::uuid""",
            job_id,
        )
    if not row:
        raise HTTPException(404, "Image job not found")

    result = dict(row)
    # created_at → ISO string for JSON serialisation
    if result.get("created_at"):
        result["created_at"] = result["created_at"].isoformat()
    return result


@router.get("")
async def list_images(user_id: str | None = None, session_id: str | None = None):
    if not user_id and not session_id:
        return []
    async with get_db() as db:
        if user_id:
            rows = await db.fetch(
                """SELECT id, concept, domain, image_url, status, created_at
                   FROM educational_images WHERE user_id = $1::uuid
                   ORDER BY created_at DESC LIMIT 20""",
                user_id,
            )
        else:
            rows = await db.fetch(
                """SELECT id, concept, domain, image_url, status, created_at
                   FROM educational_images WHERE session_id = $1::uuid
                   ORDER BY created_at DESC LIMIT 10""",
                session_id,
            )
    return [
        {**dict(r), "created_at": r["created_at"].isoformat() if r["created_at"] else None}
        for r in rows
    ]
