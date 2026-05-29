"""
StudySet processor service.
Extracts text from PDF using PyMuPDF, then uses GPT-4o to generate
concepts and flashcards. Runs as a FastAPI background task.
"""
import json
import logging

logger = logging.getLogger(__name__)


# ─── PDF extraction ───────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, int]:
    """
    Extract full text from a PDF given its raw bytes.
    Returns (full_text, page_count).
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text.strip())
    doc.close()
    return "\n\n".join(pages), len(doc)


# ─── AI generation ────────────────────────────────────────────────────────────

async def generate_concepts_and_flashcards(
    text: str,
    title: str,
    subject: str | None,
) -> dict:
    """
    Call GPT-4o with the extracted text and return structured JSON containing:
      summary, concepts[], flashcards[]
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI()

    # Truncate to ~80 000 chars ≈ 20 000 tokens — enough for ~40 pages
    truncated = text[:80_000]

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
- Keep language clear and student-friendly

--- MATERIAL ---
{truncated}"""

    response = await client.chat.completions.create(
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
) -> None:
    """
    Full processing pipeline (runs in background):
      1. Extract text from PDF
      2. Save raw_text + page_count to study_materials
      3. Call GPT-4o to generate summary, concepts, flashcards
      4. Persist everything and mark study_set status = 'ready'
    """
    from database import get_db

    # ── 1. Fetch study set metadata ──────────────────────────────────────────
    try:
        async with get_db() as db:
            ss = await db.fetchrow(
                "SELECT title, subject FROM study_sets WHERE id = $1::uuid",
                study_set_id,
            )
        if not ss:
            logger.error("[studyset] study_set %s not found", study_set_id)
            return
    except Exception as exc:
        logger.error("[studyset] DB fetch failed for %s: %s", study_set_id, exc)
        return

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
        logger.info("[studyset] %s: calling GPT-4o", study_set_id)
        result = await generate_concepts_and_flashcards(text, ss["title"], ss["subject"])
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
        logger.error("[studyset] DB save failed for %s: %s", study_set_id, exc)
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
