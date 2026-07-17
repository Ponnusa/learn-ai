"""
StudySet router.
  POST   /api/studysets                                     — create
  GET    /api/studysets                                     — list
  GET    /api/studysets/{id}                                — full detail
  GET    /api/studysets/{id}/status                         — poll status
  POST   /api/studysets/{id}/upload                         — upload PDF
  GET    /api/studysets/{id}/materials/{mid}/pdf            — proxy PDF (CORS-safe)
  POST   /api/studysets/{id}/chat                           — grounded chat
  GET    /api/studysets/{id}/conversations                  — list conversations
  POST   /api/studysets/{id}/cards/{card_id}/review         — record flashcard rating
  DELETE /api/studysets/{id}                                — delete
"""
import json as _json
import logging
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from database import get_db
from services.ai_router import openai_client, get_model
from services.credits import check_message_credit
from services.chips import generate_chips
from services.prompt_builder import build_studyset_prompt, inject_conversation_context
from services.conversation_summarizer import maybe_summarize
from services.profile_updater import update_student_profile

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
    concept_name: str | None = None      # set when student clicks a concept → seeds intro
    conversation_id: str | None = None   # None on first message; subsequent messages pass it back
    user_id: str | None = None
    session_id: str | None = None
    image_url: str | None = None         # R2 URL of a captured PDF region (vision input)
    language: str = "en"


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
async def get_study_set(study_set_id: str, user_id: str | None = None):
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
        # When logged in, surface each card's spaced-repetition due date and sort
        # cards never reviewed (or overdue) first so the deck prioritises what's due.
        if user_id:
            flashcards = await db.fetch(
                """SELECT sf.id, sf.front, sf.back, sf.order_index, sfs.due_at
                   FROM study_flashcards sf
                   LEFT JOIN study_flashcard_state sfs
                          ON sfs.flashcard_id = sf.id AND sfs.student_id = $2::uuid
                   WHERE sf.study_set_id = $1::uuid
                   ORDER BY COALESCE(sfs.due_at, TIMESTAMP '1970-01-01') ASC, sf.order_index""",
                study_set_id, user_id,
            )
        else:
            flashcards = await db.fetch(
                """SELECT id, front, back, order_index, NULL::timestamptz AS due_at
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

    now = datetime.now(tz=timezone.utc)
    return {
        **dict(ss),
        "concepts":   [dict(c) for c in concepts],
        "flashcards": [
            {**dict(f), "is_due": f["due_at"] is None or f["due_at"] <= now}
            for f in flashcards
        ],
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
    bg.add_task(process_material_bg, material_id, study_set_id, data, user_id)

    return {"material_id": material_id, "status": "processing"}


@router.get("/{study_set_id}/materials/{material_id}/pdf")
async def proxy_material_pdf(study_set_id: str, material_id: str):
    """
    Proxy the stored PDF through the backend so the browser avoids R2 CORS
    restrictions. Downloads via the authenticated R2 S3 API (same path as
    uploads) so the bucket does not need to be publicly accessible.
    """
    from fastapi.responses import Response

    async with get_db() as db:
        mat = await db.fetchrow(
            """SELECT file_url, filename FROM study_materials
               WHERE id = $1::uuid AND study_set_id = $2::uuid""",
            material_id, study_set_id,
        )
    if not mat or not mat["file_url"]:
        raise HTTPException(404, "Material PDF not found — please re-upload the file")

    import asyncio
    from urllib.parse import urlparse
    from services.manim import _make_r2_client, R2_BUCKET_NAME

    # Extract the object key from the URL path, e.g.
    # "https://pub-xxx.r2.dev/studysets/abc/file.pdf" → "studysets/abc/file.pdf"
    r2_key = urlparse(mat["file_url"]).path.lstrip('/')
    logger.info("[studyset] proxy PDF: key=%s", r2_key)

    r2 = _make_r2_client()
    if r2 and r2_key:
        try:
            # Run the blocking boto3 call (including stream read) on a thread
            def _fetch():
                obj = r2.get_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
                return obj["Body"].read()

            pdf_bytes = await asyncio.get_running_loop().run_in_executor(None, _fetch)
        except Exception as exc:
            logger.error("[studyset] R2 get_object failed for key=%s: %s", r2_key, exc)
            raise HTTPException(502, f"Could not retrieve PDF from storage: {exc}")
    else:
        # Fallback: direct HTTP fetch (requires public bucket)
        import httpx
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.get(mat["file_url"])
            if r.status_code != 200:
                raise HTTPException(502, f"Storage returned HTTP {r.status_code}")
            pdf_bytes = r.content
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Storage fetch failed: {exc}")

    safe_name = (mat["filename"] or "material.pdf").replace('"', '')
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@router.post("/{study_set_id}/chat")
async def chat_with_studyset(study_set_id: str, req: ChatRequest, bg: BackgroundTasks):
    """
    Grounded chat — answers are strictly from the study material.
    Creates a persisted conversation on first message; all turns are
    saved to messages table so history survives page refreshes.
    Supports vision: pass image_url (R2 URL of a PDF region capture).
    """
    # ── 1. Credit check ───────────────────────────────────────────────────────
    await check_message_credit(req.user_id, req.session_id)

    # ── 2. Fetch study set + materials ────────────────────────────────────────
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

    # ── 3. Get or create conversation (one per studyset per user/session) ─────
    conv_id = req.conversation_id
    if not conv_id:
        async with get_db() as db:
            existing = await db.fetchrow(
                """SELECT id FROM conversations
                   WHERE study_set_id = $1::uuid
                     AND (
                       ($2::uuid IS NOT NULL AND user_id    = $2::uuid)
                       OR ($3::uuid IS NOT NULL AND session_id = $3::uuid)
                     )
                   ORDER BY created_at ASC LIMIT 1""",
                study_set_id, req.user_id, req.session_id,
            )
        if existing:
            conv_id = str(existing["id"])
        else:
            async with get_db() as db:
                conv = await db.fetchrow(
                    """INSERT INTO conversations
                         (user_id, session_id, title, subject, study_set_id)
                       VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)
                       RETURNING id""",
                    req.user_id, req.session_id,
                    f"{ss['title']} — Study Chat", ss["subject"], study_set_id,
                )
            conv_id = str(conv["id"])

    # ── 4. Fetch history from DB + conversation context ───────────────────────
    async with get_db() as db:
        db_history = await db.fetch("""
            SELECT role, content FROM messages
            WHERE conversation_id = $1::uuid
            ORDER BY created_at DESC LIMIT 6
        """, conv_id)
        db_history = list(reversed(db_history))

        conv_row = await db.fetchrow("""
            SELECT summary, topics_covered, summarized_msg_count
            FROM conversations WHERE id = $1::uuid
        """, conv_id)

    conv_summary   = conv_row["summary"] if conv_row else None
    topics_covered = conv_row["topics_covered"] if conv_row else None

    # ── 5. Save user message (with image metadata if present) ─────────────────
    content_type = "image_url" if req.image_url else "text"
    metadata     = _json.dumps({"image_url": req.image_url}) if req.image_url else "{}"
    async with get_db() as db:
        await db.execute(
            """INSERT INTO messages (conversation_id, role, content, content_type, metadata)
               VALUES ($1::uuid, 'user', $2, $3, $4::jsonb)""",
            conv_id, req.message, content_type, metadata,
        )
        if req.session_id:
            await db.execute(
                "UPDATE anonymous_sessions SET msg_count = msg_count + 1 WHERE id = $1",
                req.session_id,
            )

    # ── 6. Build system prompt (grounded + personalised + continuity) ─────────
    full_text     = "\n\n".join(r["raw_text"] or "" for r in mat_rows if r["raw_text"])
    system_prompt = await build_studyset_prompt(
        title=ss["title"],
        subject=ss["subject"],
        material_text=full_text,
        user_id=req.user_id,
        language=req.language,
    )
    system_prompt = inject_conversation_context(system_prompt, conv_summary, topics_covered)

    # ── 7. Build messages for AI ──────────────────────────────────────────────
    ai_messages = [{"role": "system", "content": system_prompt}]
    for h in db_history:
        ai_messages.append({"role": h["role"], "content": h["content"]})

    # Concept-seeded intro: structured lesson format (only on very first message)
    if req.concept_name and not db_history:
        base_text = (
            f'Give me a thorough lesson on "{req.concept_name}" based on the study material. '
            f'Structure your response as:\n'
            f'1. **Definition** — what it is in plain terms\n'
            f'2. **Key points** — the most important things to understand\n'
            f'3. **From the material** — quote or paraphrase the most relevant section\n'
            f'4. **Example** — a concrete example that makes it click\n\n'
            f'Keep it focused and student-friendly.'
        )
    else:
        base_text = req.message

    if req.image_url:
        user_content = [
            {"type": "text", "text": base_text},
            {"type": "image_url", "image_url": {"url": req.image_url, "detail": "high"}},
        ]
    else:
        user_content = base_text

    ai_messages.append({"role": "user", "content": user_content})

    # ── 8. Call AI (gpt-4o via model router) ─────────────────────────────────
    response = await openai_client.chat.completions.create(
        model=get_model("studyset_chat"),
        messages=ai_messages,
        max_tokens=1500,
        temperature=0.3,
    )
    reply = response.choices[0].message.content

    # ── 9. Generate contextual chips ──────────────────────────────────────────
    chips = await generate_chips(reply)

    # ── 10. Save AI reply ─────────────────────────────────────────────────────
    async with get_db() as db:
        ai_msg = await db.fetchrow(
            """INSERT INTO messages (conversation_id, role, content, metadata)
               VALUES ($1::uuid, 'assistant', $2, $3::jsonb) RETURNING id""",
            conv_id, reply, _json.dumps({"chips": chips}),
        )
        msg_count_row = await db.fetchrow(
            "SELECT COUNT(*) AS cnt FROM messages WHERE conversation_id = $1::uuid", conv_id
        )
        msg_count = msg_count_row["cnt"]

    # ── 11. Background tasks ──────────────────────────────────────────────────
    bg.add_task(maybe_summarize, conv_id, msg_count)
    if req.user_id and msg_count % 5 == 0:
        bg.add_task(update_student_profile, req.user_id, conv_id, ss["subject"] or "General")

    return {
        "reply":           reply,
        "chips":           chips,
        "conversation_id": conv_id,
        "message_id":      str(ai_msg["id"]),
    }


@router.post("/{study_set_id}/debug-prompt")
async def debug_studyset_prompt(study_set_id: str, req: ChatRequest):
    """
    DEV — returns the exact system prompt + message history that would be
    sent to the AI for this studyset chat, without calling the AI.
    """
    async with get_db() as db:
        ss = await db.fetchrow(
            "SELECT title, subject FROM study_sets WHERE id = $1::uuid", study_set_id
        )
        if not ss:
            raise HTTPException(404, "Study set not found")
        mat_rows = await db.fetch(
            """SELECT raw_text FROM study_materials
               WHERE study_set_id = $1::uuid AND status = 'ready'
               ORDER BY created_at""",
            study_set_id,
        )

    conv_id        = req.conversation_id
    conv_summary   = None
    topics_covered = None
    history: list  = []

    if conv_id:
        async with get_db() as db:
            conv_row = await db.fetchrow("""
                SELECT summary, topics_covered
                FROM conversations WHERE id = $1::uuid
            """, conv_id)
            if conv_row:
                conv_summary   = conv_row["summary"]
                topics_covered = conv_row["topics_covered"]

            rows = await db.fetch("""
                SELECT role, content FROM messages
                WHERE conversation_id = $1::uuid
                ORDER BY created_at DESC LIMIT 6
            """, conv_id)
            history = list(reversed(rows))

    full_text     = "\n\n".join(r["raw_text"] or "" for r in mat_rows if r["raw_text"])
    system_prompt = await build_studyset_prompt(
        title=ss["title"],
        subject=ss["subject"],
        material_text=full_text,
        user_id=req.user_id,
        language=req.language,
    )
    system_prompt = inject_conversation_context(system_prompt, conv_summary, topics_covered)

    msgs = [{"role": h["role"], "content": h["content"]} for h in history]

    return {
        "model":               get_model("studyset_chat"),
        "system_prompt":       system_prompt,
        "system_prompt_chars": len(system_prompt),
        "material_chars":      len(full_text),
        "history":             msgs,
        "history_count":       len(msgs),
        "conversation_id":     conv_id,
        "subject":             ss["subject"],
    }


@router.get("/{study_set_id}/conversations")
async def get_studyset_conversations(study_set_id: str):
    """List all conversations linked to this study set, with counts."""
    async with get_db() as db:
        rows = await db.fetch(
            """SELECT
                 c.id, c.title, c.created_at,
                 COUNT(DISTINCT m.id) FILTER (WHERE m.role = 'user') AS message_count,
                 COUNT(DISTINCT v.id)                                 AS video_count,
                 COUNT(DISTINCT q.id)                                 AS quiz_count
               FROM conversations c
               LEFT JOIN messages m ON m.conversation_id = c.id
               LEFT JOIN videos   v ON v.conversation_id = c.id
               LEFT JOIN quizzes  q ON q.conversation_id = c.id
               WHERE c.study_set_id = $1::uuid
               GROUP BY c.id
               ORDER BY c.created_at DESC
               LIMIT 30""",
            study_set_id,
        )
    return [dict(r) for r in rows]


@router.post("/{study_set_id}/cards/{card_id}/review")
async def review_card(study_set_id: str, card_id: str, req: ReviewRequest):
    """Record a flashcard rating: 1=again  2=hard  3=good  4=easy. Schedules next review (SM-2-style)."""
    from services.srs import next_state, DEFAULT_EASE

    if req.rating not in (1, 2, 3, 4):
        raise HTTPException(400, "rating must be 1, 2, 3, or 4")

    async with get_db() as db:
        await db.execute(
            """INSERT INTO study_card_reviews (user_id, flashcard_id, rating)
               VALUES ($1::uuid, $2::uuid, $3)""",
            req.user_id, card_id, req.rating,
        )

        state = await db.fetchrow(
            """SELECT repetitions, ease_factor, interval_days
               FROM study_flashcard_state WHERE student_id = $1::uuid AND flashcard_id = $2::uuid""",
            req.user_id, card_id,
        )
        repetitions, ease_factor, interval_days = (
            (state["repetitions"], state["ease_factor"], state["interval_days"]) if state
            else (0, DEFAULT_EASE, 0.0)
        )
        repetitions, ease_factor, interval_days, due_at = next_state(
            req.rating, repetitions, ease_factor, interval_days
        )

        await db.execute("""
            INSERT INTO study_flashcard_state
              (student_id, flashcard_id, repetitions, ease_factor, interval_days, due_at, last_reviewed_at)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, NOW())
            ON CONFLICT (student_id, flashcard_id)
            DO UPDATE SET repetitions = $3, ease_factor = $4, interval_days = $5,
                          due_at = $6, last_reviewed_at = NOW()
        """, req.user_id, card_id, repetitions, ease_factor, interval_days, due_at)

    return {"ok": True, "due_at": due_at.isoformat(), "interval_days": interval_days}


@router.delete("/{study_set_id}")
async def delete_study_set(study_set_id: str):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM study_sets WHERE id = $1::uuid", study_set_id
        )
    return {"ok": True}
