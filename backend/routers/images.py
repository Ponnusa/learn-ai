"""
Educational Image Generator API

  POST /api/images/generate        — start a generation job (async)
  GET  /api/images/{job_id}        — poll job status / retrieve result
  GET  /api/images                 — list images (by user/session/conversation/study_set)
  DELETE /api/images/{job_id}      — delete an image job
  POST /api/images/{job_id}/retry  — retry a failed image job
"""
import uuid
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["images"])


class GenerateRequest(BaseModel):
    concept:         str
    user_id:         str | None = None
    session_id:      str | None = None
    conversation_id: str | None = None
    study_set_id:    str | None = None
    message_id:      str | None = None


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
            """INSERT INTO educational_images
               (id, user_id, session_id, conversation_id, study_set_id, message_id, concept, status)
               VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, $6, $7, 'processing')""",
            job_id, req.user_id, req.session_id,
            req.conversation_id, req.study_set_id, req.message_id, concept,
        )

    from services.educational_image import process_image_job
    bg.add_task(process_image_job, job_id, concept, req.user_id, req.session_id)

    logger.info("[edu-img] job created: %s conv=%s ss=%s", job_id[:8],
                (req.conversation_id or "")[:8], (req.study_set_id or "")[:8])
    return {"jobId": job_id, "status": "processing"}


@router.get("/{job_id}")
async def get_image_job(job_id: str):
    async with get_db() as db:
        row = await db.fetchrow(
            """SELECT id, concept, domain, spec, prompt, image_url, status, error_msg,
                      conversation_id, study_set_id, message_id,
                      knowledge_model, diagram_plan, critic_report,
                      diagram_type, generation_attempts, description, created_at
               FROM educational_images WHERE id = $1::uuid""",
            job_id,
        )
    if not row:
        raise HTTPException(404, "Image job not found")

    result = dict(row)
    if result.get("created_at"):
        result["created_at"] = result["created_at"].isoformat()
    for field in ("conversation_id", "study_set_id"):
        if result.get(field):
            result[field] = str(result[field])
    return result


@router.get("")
async def list_images(
    user_id:         str | None = None,
    session_id:      str | None = None,
    conversation_id: str | None = None,
    study_set_id:    str | None = None,
):
    async with get_db() as db:
        if conversation_id:
            rows = await db.fetch(
                """SELECT id, concept, domain, image_url, status, error_msg,
                          message_id, spec, description, created_at
                   FROM educational_images WHERE conversation_id = $1::uuid
                   ORDER BY created_at ASC""",
                conversation_id,
            )
        elif study_set_id:
            rows = await db.fetch(
                """SELECT id, concept, domain, image_url, status, error_msg,
                          message_id, spec, description, created_at
                   FROM educational_images WHERE study_set_id = $1::uuid
                   ORDER BY created_at ASC""",
                study_set_id,
            )
        elif user_id:
            rows = await db.fetch(
                """SELECT id, concept, domain, image_url, status, error_msg,
                          message_id, spec, description, created_at
                   FROM educational_images WHERE user_id = $1::uuid
                   ORDER BY created_at DESC LIMIT 20""",
                user_id,
            )
        elif session_id:
            rows = await db.fetch(
                """SELECT id, concept, domain, image_url, status, error_msg,
                          message_id, spec, description, created_at
                   FROM educational_images WHERE session_id = $1::uuid
                   ORDER BY created_at DESC LIMIT 10""",
                session_id,
            )
        else:
            return []

    return [
        {**dict(r), "created_at": r["created_at"].isoformat() if r["created_at"] else None}
        for r in rows
    ]


@router.delete("/{job_id}")
async def delete_image(job_id: str):
    async with get_db() as db:
        result = await db.execute(
            "DELETE FROM educational_images WHERE id = $1::uuid", job_id
        )
    if result == "DELETE 0":
        raise HTTPException(404, "Image job not found")
    logger.info("[edu-img] deleted: %s", job_id[:8])
    return {"deleted": True}


@router.post("/{job_id}/retry")
async def retry_image(job_id: str, bg: BackgroundTasks):
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT concept, user_id, session_id FROM educational_images WHERE id = $1::uuid",
            job_id,
        )
        if not row:
            raise HTTPException(404, "Image job not found")

        await db.execute(
            """UPDATE educational_images
               SET status='processing', error_msg=NULL, image_url=NULL,
                   domain=NULL, spec='{}', prompt=NULL
               WHERE id = $1::uuid""",
            job_id,
        )

    from services.educational_image import process_image_job
    uid = str(row["user_id"]) if row["user_id"] else None
    sid = str(row["session_id"]) if row["session_id"] else None
    bg.add_task(process_image_job, job_id, row["concept"], uid, sid)

    logger.info("[edu-img] retry: %s", job_id[:8])
    return {"jobId": job_id, "status": "processing"}
