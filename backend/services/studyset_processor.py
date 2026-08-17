"""
StudySet processor service.
Extracts text from PDF using PyMuPDF, then uses GPT-4o to generate
concepts and flashcards. Runs as a FastAPI background task.
"""
import json
import logging
from services.ai_router import openai_client

logger = logging.getLogger(__name__)


# ─── PDF extraction ───────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, int]:
    """
    Extract full text from a PDF given its raw bytes.
    Returns (full_text, page_count).
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_count = len(doc)          # must read before close()
    pages: list[str] = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text.strip())
    doc.close()
    return "\n\n".join(pages), page_count


def extract_pages_from_pdf(file_bytes: bytes) -> list[str]:
    """Per-page text, index 0 = page 1. Used for table-of-contents detection and page-range slicing."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = [page.get_text("text") or "" for page in doc]
    doc.close()
    return pages


def is_sparse_text(text: str, page_count: int) -> bool:
    """True when PyMuPDF returned too little text — almost certainly a scanned PDF."""
    return len(text.strip()) / max(page_count, 1) < 80


async def extract_text_vision(file_bytes: bytes) -> tuple[str, int]:
    """OCR a scanned PDF using Claude Haiku vision in batches of 5 pages.
    Returns (full_text, page_count). Use when extract_text_from_pdf yields sparse text."""
    import fitz, base64
    import anthropic

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_count = len(doc)
    mat = fitz.Matrix(1.5, 1.5)
    client = anthropic.AsyncAnthropic()
    all_text: list[str] = []
    BATCH = 5

    for batch_start in range(0, page_count, BATCH):
        batch_end = min(batch_start + BATCH, page_count)
        content: list[dict] = []
        for idx in range(batch_start, batch_end):
            pix = doc[idx].get_pixmap(matrix=mat)
            b64 = base64.standard_b64encode(pix.tobytes("png")).decode()
            content.append({"type": "text", "text": f"--- Page {idx + 1} ---"})
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/png", "data": b64,
            }})
        content.append({"type": "text", "text": (
            "Extract all text from these pages exactly as written. "
            "Preserve headings, equations, lists, and paragraph structure. "
            "Return only the extracted text, no commentary."
        )})
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )
        all_text.append(resp.content[0].text)

    doc.close()
    return "\n\n".join(all_text), page_count


# ─── AI generation ────────────────────────────────────────────────────────────

_LANGUAGE_NAMES = {'fi': 'Finnish', 'sv': 'Swedish', 'es': 'Spanish', 'fr': 'French'}


async def generate_concepts_and_flashcards(
    text: str,
    title: str,
    subject: str | None,
    language: str = 'en',
) -> dict:
    """
    Call GPT-4o with the extracted text and return structured JSON containing:
      summary, concepts[], flashcards[]
    """
    # Truncate to ~80 000 chars ≈ 20 000 tokens — enough for ~40 pages
    truncated = text[:80_000]

    lang_instruction = ""
    if language in _LANGUAGE_NAMES:
        lang_name = _LANGUAGE_NAMES[language]
        lang_instruction = f"\n\nIMPORTANT: Generate ALL content (summary, concept names, definitions, explanations, flashcard fronts and backs) in {lang_name}. Do not use English."

    prompt = f"""You are an expert educator. Analyze the study material below and extract structured learning content.

Title: {title}
Subject: {subject or "General"}

Return ONLY a valid JSON object with this exact structure — no prose, no markdown fences:
{{
  "summary": "2-3 sentence overview of the entire material",
  "concepts": [
    {{
      "name": "concept name",
      "definition": "clear 1-2 sentence definition",
      "explanation": "2-4 sentence explanation with context and examples"
    }}
  ],
  "flashcards": [
    {{
      "front": "question or term",
      "back": "answer or definition"
    }}
  ]
}}

Requirements:
- Extract 10-20 key concepts (most important ideas, terms, principles)
- Generate 20-30 flashcards mixing term→definition and question→answer formats
- Focus on testable, examinable content
- Keep language clear and student-friendly{lang_instruction}

--- MATERIAL ---
{truncated}"""

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=4000,
        temperature=0.3,
    )

    return json.loads(response.choices[0].message.content)


# ─── Background task ──────────────────────────────────────────────────────────

async def process_material_bg(
    material_id: str,
    study_set_id: str,
    file_bytes: bytes,
    user_id: str | None = None,
) -> None:
    """
    Full processing pipeline (runs in background):
      1. Extract text from PDF
      2. Save raw_text + page_count to study_materials
      3. Call GPT-4o to generate summary, concepts, flashcards
      4. Persist everything and mark study_set status = 'ready'
    """
    from database import get_db

    # ── 1. Fetch study set metadata + user language ──────────────────────────
    try:
        async with get_db() as db:
            ss = await db.fetchrow(
                "SELECT title, subject FROM study_sets WHERE id = $1::uuid",
                study_set_id,
            )
            language = 'en'
            if user_id:
                lang_row = await db.fetchval(
                    "SELECT language FROM users WHERE id = $1::uuid", user_id
                )
                if lang_row:
                    language = lang_row
            # Check whether R2 upload succeeded at request time
            existing_url = await db.fetchval(
                "SELECT file_url FROM study_materials WHERE id = $1::uuid", material_id
            )
        if not ss:
            logger.error("[studyset] study_set %s not found", study_set_id)
            return
    except Exception as exc:
        logger.error("[studyset] DB fetch failed for %s: %s", study_set_id, exc)
        return

    # ── 1b. Retry R2 upload if it failed at request time ─────────────────────
    if not existing_url:
        try:
            import uuid as _uuid
            from datetime import datetime, timezone
            from services.manim import _make_r2_client, R2_BUCKET_NAME, R2_PUBLIC_URL
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            uid = _uuid.uuid4().hex[:8]
            r2_key = f"studysets/{study_set_id}/{ts}_{uid}.pdf"
            r2 = _make_r2_client()
            if r2:
                r2.put_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=r2_key,
                    Body=file_bytes,
                    ContentType="application/pdf",
                )
                recovered_url = f"{R2_PUBLIC_URL.rstrip('/')}/{r2_key}"
                async with get_db() as db:
                    await db.execute(
                        "UPDATE study_materials SET file_url = $1 WHERE id = $2::uuid",
                        recovered_url, material_id,
                    )
                logger.info("[studyset] %s: R2 retry succeeded → %s", study_set_id, r2_key)
        except Exception as exc:
            logger.warning("[studyset] %s: R2 retry also failed: %s", study_set_id, exc)

    # ── 2. Extract PDF text ──────────────────────────────────────────────────
    try:
        logger.info("[studyset] %s: extracting PDF text", study_set_id)
        text, page_count = extract_text_from_pdf(file_bytes)
        char_count = len(text)
        logger.info("[studyset] %s: %d pages, %d chars", study_set_id, page_count, char_count)
    except Exception as exc:
        logger.error("[studyset] PDF extraction failed for %s: %s", study_set_id, exc)
        await _mark_failed(material_id, study_set_id, f"PDF extraction failed: {exc}")
        return

    # ── 3. Persist raw text ──────────────────────────────────────────────────
    try:
        async with get_db() as db:
            await db.execute(
                """UPDATE study_materials
                   SET raw_text = $1, page_count = $2, char_count = $3
                   WHERE id = $4::uuid""",
                text, page_count, char_count, material_id,
            )
    except Exception as exc:
        logger.error("[studyset] raw_text save failed: %s", exc)
        # Non-fatal — continue

    # ── 4. AI generation ─────────────────────────────────────────────────────
    try:
        logger.info("[studyset] %s: calling GPT-4o (language=%s)", study_set_id, language)
        result = await generate_concepts_and_flashcards(text, ss["title"], ss["subject"], language)
    except Exception as exc:
        logger.error("[studyset] AI generation failed for %s: %s", study_set_id, exc)
        await _mark_failed(material_id, study_set_id, f"AI generation failed: {exc}")
        return

    summary   = result.get("summary", "")
    concepts  = result.get("concepts", [])
    flashcards = result.get("flashcards", [])

    logger.info(
        "[studyset] %s: AI done — %d concepts, %d flashcards",
        study_set_id, len(concepts), len(flashcards),
    )

    # ── 5. Persist to DB ─────────────────────────────────────────────────────
    try:
        async with get_db() as db:
            # Concepts
            logger.info("[studyset] %s: saving %d concepts", study_set_id, len(concepts))
            for i, c in enumerate(concepts):
                await db.execute(
                    """INSERT INTO study_concepts
                         (study_set_id, name, definition, explanation, order_index)
                       VALUES ($1::uuid, $2, $3, $4, $5)""",
                    study_set_id,
                    c.get("name", ""),
                    c.get("definition", ""),
                    c.get("explanation", ""),
                    i,
                )

            # Flashcards
            logger.info("[studyset] %s: saving %d flashcards", study_set_id, len(flashcards))
            for i, f in enumerate(flashcards):
                await db.execute(
                    """INSERT INTO study_flashcards
                         (study_set_id, front, back, order_index)
                       VALUES ($1::uuid, $2, $3, $4)""",
                    study_set_id,
                    f.get("front", ""),
                    f.get("back", ""),
                    i,
                )

            # Mark both material and study set as ready
            await db.execute(
                "UPDATE study_materials SET status = 'ready' WHERE id = $1::uuid",
                material_id,
            )
            await db.execute(
                """UPDATE study_sets
                   SET status = 'ready', summary = $1, updated_at = NOW()
                   WHERE id = $2::uuid""",
                summary, study_set_id,
            )

        logger.info("[studyset] %s: ready ✓", study_set_id)

    except Exception as exc:
        logger.error("[studyset] DB save failed for %s: %s — %r", study_set_id, exc, exc)
        import traceback
        logger.error("[studyset] traceback: %s", traceback.format_exc())
        await _mark_failed(material_id, study_set_id, f"DB save failed: {exc}")


async def _mark_failed(material_id: str, study_set_id: str, reason: str) -> None:
    from database import get_db
    try:
        async with get_db() as db:
            await db.execute(
                "UPDATE study_materials SET status = 'failed', error_msg = $1 WHERE id = $2::uuid",
                reason, material_id,
            )
            await db.execute(
                "UPDATE study_sets SET status = 'failed', updated_at = NOW() WHERE id = $1::uuid",
                study_set_id,
            )
    except Exception as exc:
        logger.error("[studyset] also failed to write failure status: %s", exc)
