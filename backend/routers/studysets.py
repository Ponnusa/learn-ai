"""
StudySet router.
  POST   /api/studysets                         — create a new study set
  GET    /api/studysets                         — list (by user_id or session_id)
  GET    /api/studysets/{id}                    — full detail (+ concepts + flashcards)
  GET    /api/studysets/{id}/status             — lightweight poll during processing
  POST   /api/studysets/{id}/upload             — upload PDF (multipart)
  POST   /api/studysets/{id}/chat               — grounded chat
  POST   /api/studysets/{id}/cards/{card_id}/review  — record flashcard rating
  DELETE /api/studysets/{id}                    — delete
"""
import logging
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studysets", tags=["studysets"])

_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB


# ─── Request models ───────────────────────────────────────────────────────────

class CreateStudySetRequest(BaseModel):
    title: str
    subject: str | None = None
    description: str | None = None
    user_id: str | None = None
    session_id: str | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []   # [{role, content}, ...]


class ReviewRequest(BaseModel):
    user_id: str
    rating: int   # 1=again  2=hard  3=good  4=easy


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("")
async def create_study_set(req: CreateStudySetRequest):
    async with get_db() as db:
        row = await db.fetchrow(
            """INSERT INTO study_sets
                 (user_id, session_id, title, subject, description, status)
               VALUES ($1::uuid, $2::uuid, $3, $4, $5, 'empty')
               RETURNING id, title, subject, description, status, created_at""",
            req.user_id, req.session_id, req.title, req.subject, req.description,
        )
    return dict(row)


@router.get("")
async def list_study_sets(
    user_id: str | None = None,
    session_id: str | None = None,
):
    if not user_id and not session_id:
        return []

    filter_col = "ss.user_id = $1::uuid" if user_id else "ss.session_id = $1::uuid"
    param = user_id or session_id

    async with get_db() as db:
        rows = await db.fetch(
            f"""SELECT ss.id, ss.title, ss.subject, ss.status, ss.summary,
                       ss.created_at,
                       COUNT(DISTINCT sc.id) AS concept_count,
                       COUNT(DISTINCT sf.id) AS flashcard_count
                FROM study_sets ss
                LEFT JOIN study_concepts   sc ON sc.study_set_id = ss.id
                LEFT JOIN study_flashcards sf ON sf.study_set_id = ss.id
                WHERE {filter_col}
                GROUP BY ss.id
                ORDER BY ss.created_at DESC
                LIMIT 50""",
            param,
        )
    return [dict(r) for r in rows]


@router.get("/{study_set_id}")
async def get_study_set(study_set_id: str):
    async with get_db() as db:
        ss = await db.fetchrow(
            """SELECT id, title, subject, description, status, summary,
                      created_at, updated_at
               FROM study_sets WHERE id = $1::uuid""",
            study_set_id,
        )
        if not ss:
            raise HTTPException(404, "Study set not found")

        concepts = await db.fetch(
            """SELECT id, name, definition, explanation, order_index
               FROM study_concepts WHERE study_set_id = $1::uuid
               ORDER BY order_index""",
            study_set_id,
        )
        flashcards = await db.fetch(
            """SELECT id, front, back, order_index
               FROM study_flashcards WHERE study_set_id = $1::uuid
               ORDER BY order_index""",
            study_set_id,
        )
        materials = await db.fetch(
            """SELECT id, filename, page_count, char_count, status, error_msg, created_at
               FROM study_materials WHERE study_set_id = $1::uuid
               ORDER BY created_at""",
            study_set_id,
        )

    return {
        **dict(ss),
        "concepts":   [dict(c) for c in concepts],
        "flashcards": [dict(f) for f in flashcards],
        "materials":  [dict(m) for m in materials],
    }


@router.get("/{study_set_id}/status")
async def get_study_set_status(study_set_id: str):
    async with get_db() as db:
        row = await db.fetchrow(
            """SELECT ss.status, ss.summary,
                      COUNT(DISTINCT sc.id) AS concept_count,
                      COUNT(DISTINCT sf.id) AS flashcard_count
               FROM study_sets ss
               LEFT JOIN study_concepts   sc ON sc.study_set_id = ss.id
               LEFT JOIN study_flashcards sf ON sf.study_set_id = ss.id
               WHERE ss.id = $1::uuid
               GROUP BY ss.id, ss.status, ss.summary""",
            study_set_id,
        )
    if not row:
        raise HTTPException(404, "Study set not found")
    return dict(row)


@router.post("/{study_set_id}/upload")
async def upload_material(
    study_set_id: str,
    bg: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str | None = Form(None),
):
    """Accept a PDF, store it in R2, then kick off background processing."""
    # Validate file type
    ct = file.content_type or ""
    fname = (file.filename or "").lower()
    if "pdf" not in ct and not fname.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    data = await file.read()
    if len(data) > _MAX_PDF_BYTES:
        raise HTTPException(413, "PDF too large (max 50 MB)")
    if len(data) == 0:
        raise HTTPException(400, "Empty file")

    # Verify study set exists
    async with get_db() as db:
        ss = await db.fetchrow(
            "SELECT id FROM study_sets WHERE id = $1::uuid", study_set_id
        )
    if not ss:
        raise HTTPException(404, "Study set not found")

    # Upload to R2 (best-effort — don't fail the request if R2 is down)
    from services.manim import _make_r2_client, R2_BUCKET_NAME, R2_PUBLIC_URL

    ts      = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    uid     = _uuid.uuid4().hex[:8]
    r2_key  = f"studysets/{study_set_id}/{ts}_{uid}.pdf"
    file_url = None

    r2 = _make_r2_client()
    if r2:
        try:
            r2.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=r2_key,
                Body=data,
                ContentType="application/pdf",
            )
            file_url = f"{R2_PUBLIC_URL.rstrip('/')}/{r2_key}"
            logger.info("[studyset] PDF uploaded to R2: %s", r2_key)
        except Exception as exc:
            logger.warning("[studyset] R2 upload failed (continuing without): %s", exc)

    # Insert material record + flip study set to 'processing'
    async with get_db() as db:
        mat = await db.fetchrow(
            """INSERT INTO study_materials
                 (study_set_id, filename, file_url, status)
               VALUES ($1::uuid, $2, $3, 'processing')
               RETURNING id""",
            study_set_id, file.filename or "upload.pdf", file_url,
        )
        await db.execute(
            "UPDATE study_sets SET status = 'processing', updated_at = NOW() WHERE id = $1::uuid",
            study_set_id,
        )

    material_id = str(mat["id"])

    # Kick off background processing
    from services.studyset_processor import process_material_bg
    bg.add_task(process_material_bg, material_id, study_set_id, data)

    return {"material_id": material_id, "status": "processing"}


@router.post("/{study_set_id}/chat")
async def chat_with_studyset(study_set_id: str, req: ChatRequest):
    """Answer questions grounded strictly in the study set's material."""
    async with get_db() as db:
        ss = await db.fetchrow(
            "SELECT title, subject, summary FROM study_sets WHERE id = $1::uuid",
            study_set_id,
        )
        if not ss:
            raise HTTPException(404, "Study set not found")

        mat_rows = await db.fetch(
            """SELECT raw_text FROM study_materials
               WHERE study_set_id = $1::uuid AND status = 'ready'
               ORDER BY created_at""",
            study_set_id,
        )

    if not mat_rows:
        raise HTTPException(400, "No processed material yet — please wait for processing to finish")

    # Build context (truncate to ~60 000 chars to leave room for conversation)
    full_text = "\n\n".join(r["raw_text"] or "" for r in mat_rows if r["raw_text"])
    context   = full_text[:60_000]

    system_prompt = (
        f'You are a focused tutor for the study set "{ss["title"]}" '
        f'({ss["subject"] or "General"}).\n\n'
        "Answer the student's questions ONLY based on the material provided below. "
        "If the answer is not in the material, say so clearly — do not guess. "
        "Be concise, clear, and educational. Cite specific points from the material when helpful.\n\n"
        "--- STUDY MATERIAL ---\n"
        f"{context}\n"
        "--- END OF MATERIAL ---"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in req.history[-10:]:   # last 10 turns of context
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": req.message})

    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=800,
        temperature=0.3,
    )

    return {"reply": response.choices[0].message.content}


@router.post("/{study_set_id}/cards/{card_id}/review")
async def review_card(study_set_id: str, card_id: str, req: ReviewRequest):
    """Record a flashcard rating: 1=again  2=hard  3=good  4=easy."""
    if req.rating not in (1, 2, 3, 4):
        raise HTTPException(400, "rating must be 1, 2, 3, or 4")

    async with get_db() as db:
        await db.execute(
            """INSERT INTO study_card_reviews (user_id, flashcard_id, rating)
               VALUES ($1::uuid, $2::uuid, $3)""",
            req.user_id, card_id, req.rating,
        )
    return {"ok": True}


@router.delete("/{study_set_id}")
async def delete_study_set(study_set_id: str):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM study_sets WHERE id = $1::uuid", study_set_id
        )
    return {"ok": True}
