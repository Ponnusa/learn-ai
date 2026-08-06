"""
Lab Sheet — AI-drafted, teacher-edited, student-printed lab procedures.

Content structure (stored as JSONB):
  objective        : str
  materials        : list[str]
  safety           : list[str]
  procedure        : list[str]   — numbered steps
  data_table       : { title: str, headers: list[str], rows: int }
  analysis_questions: list[str]
  conclusion_prompt : str

Endpoints:
  POST /api/lab-sheets/{concept_id}/generate   — AI draft (optional PDF upload)
  GET  /api/lab-sheets/{concept_id}            — fetch current sheet
  PUT  /api/lab-sheets/{concept_id}            — save edits
  POST /api/lab-sheets/{concept_id}/publish    — toggle published
"""
import json
import logging

import fitz  # PyMuPDF
from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from database import get_db
from routers.auth import decode_jwt

router = APIRouter(prefix="/api/lab-sheets", tags=["lab-sheets"])
log    = logging.getLogger(__name__)

_TEACHER_TYPES = {"teacher", "institution_admin", "super_admin"}

EMPTY_CONTENT = {
    "objective":          "",
    "materials":          [],
    "safety":             [],
    "procedure":          [],
    "data_table":         {"title": "Data Table", "headers": [], "rows": 6},
    "analysis_questions": [],
    "conclusion_prompt":  "",
}


async def _assert_teacher(authorization: str, concept_id: str, db):
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    row = await db.fetchrow("SELECT account_type FROM users WHERE id = $1::uuid", user_id)
    if not row or row["account_type"] not in _TEACHER_TYPES:
        raise HTTPException(403, "Teachers only")
    concept = await db.fetchrow(
        "SELECT cc.id FROM course_concepts cc JOIN course_units cu ON cu.id = cc.unit_id "
        "JOIN courses c ON c.id = cu.course_id WHERE cc.id = $1::uuid AND c.teacher_id = $2::uuid",
        concept_id, user_id,
    )
    if not concept:
        raise HTTPException(403, "Not your concept")
    return user_id


# ── GET — fetch lab sheet (teacher or enrolled student) ───────────────────────

@router.get("/{concept_id}")
async def get_lab_sheet(concept_id: str, authorization: str = Header(...)):
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        user = await db.fetchrow("SELECT account_type FROM users WHERE id = $1::uuid", user_id)
        if not user:
            raise HTTPException(403, "Unauthorized")

        sheet = await db.fetchrow(
            "SELECT content, status FROM lab_sheets WHERE concept_id = $1::uuid", concept_id
        )

        # Students only see published sheets
        if user["account_type"] not in _TEACHER_TYPES:
            if not sheet or sheet["status"] != "published":
                return {"status": "none", "content": None}

    if not sheet:
        return {"status": "none", "content": None}

    return {"status": sheet["status"], "content": sheet["content"]}


# ── POST generate — AI draft ──────────────────────────────────────────────────

@router.post("/{concept_id}/generate")
async def generate_lab_sheet(
    concept_id:  str,
    authorization: str = Header(...),
    lab_pdf:     UploadFile | None = File(None),
):
    async with get_db() as db:
        await _assert_teacher(authorization, concept_id, db)

        concept = await db.fetchrow("""
            SELECT cc.title, cc.source_text, cc.ai_summary,
                   COALESCE(cc.suggested_prompts, '[]'::jsonb) AS suggested_prompts,
                   cur.teks_codes, cur.driving_question, cur.grade_level
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c ON c.id = cu.course_id
            LEFT JOIN curriculum_contexts cur ON cur.id = c.curriculum_context_id
            WHERE cc.id = $1::uuid
        """, concept_id)

    if not concept:
        raise HTTPException(404, "Concept not found")

    # Extract text from uploaded lab manual PDF (optional)
    lab_text = ""
    if lab_pdf and lab_pdf.filename:
        try:
            pdf_bytes = await lab_pdf.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            lab_text = "\n".join(page.get_text() for page in doc)[:6000]
        except Exception as e:
            log.warning("Lab PDF parse failed: %s", e)

    source = (concept["ai_summary"] or concept["source_text"] or "")[:5000]
    teks   = ", ".join(concept["teks_codes"] or []) if concept["teks_codes"] else ""
    grade  = concept.get("grade_level") or "6th grade"

    system_prompt = (
        f"You are an expert {grade} science teacher. "
        f"Generate a concise lab sheet for a hands-on class activity based on the lesson content provided. "
        f"Output ONLY valid JSON matching this exact structure:\n"
        f'{{"objective":"<one sentence>","materials":["<item>",...],"safety":["<rule>",...],'
        f'"procedure":["<step 1>","<step 2>",...],"data_table":{{"title":"<title>",'
        f'"headers":["<col1>","<col2>",...],"rows":<int 4-8>}},'
        f'"analysis_questions":["<q1>","<q2>","<q3>"],"conclusion_prompt":"<prompt>"}}\n'
        f"Rules:\n"
        f"- 5-8 numbered procedure steps (clear, imperative, safe for 6th graders)\n"
        f"- 2-4 data table column headers students fill on paper\n"
        f"- 3-4 analysis questions aligned to TEKS {teks}\n"
        f"- Safety: 2-3 short rules relevant to this specific activity\n"
        f"- No diagrams, no LaTeX, plain English only\n"
        f"- Output ONLY the JSON object, no markdown, no explanation"
    )

    user_msg = f"Lesson: {concept['title']}\n"
    if teks:
        user_msg += f"TEKS: {teks}\n"
    if concept.get("driving_question"):
        user_msg += f"Driving question: {concept['driving_question']}\n"
    user_msg += f"\nLesson content:\n{source}"
    if lab_text:
        user_msg += f"\n\nLab manual excerpt:\n{lab_text}"

    try:
        from services.ai_router import openai_client
        resp = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.4,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )
        content = json.loads(resp.choices[0].message.content)
    except Exception as e:
        log.exception("Lab sheet generation failed: %s", e)
        raise HTTPException(502, f"AI generation failed: {e}")

    # Upsert
    async with get_db() as db:
        await db.execute("""
            INSERT INTO lab_sheets (concept_id, status, content)
            VALUES ($1::uuid, 'draft', $2::jsonb)
            ON CONFLICT (concept_id) DO UPDATE SET content = $2::jsonb, status = 'draft', updated_at = NOW()
        """, concept_id, json.dumps(content))

    return {"status": "draft", "content": content}


# ── PUT — save teacher edits ──────────────────────────────────────────────────

class SaveLabSheetRequest(BaseModel):
    content: dict


@router.put("/{concept_id}")
async def save_lab_sheet(concept_id: str, req: SaveLabSheetRequest, authorization: str = Header(...)):
    async with get_db() as db:
        await _assert_teacher(authorization, concept_id, db)
        existing = await db.fetchval("SELECT status FROM lab_sheets WHERE concept_id = $1::uuid", concept_id)
        status = existing or "draft"
        await db.execute("""
            INSERT INTO lab_sheets (concept_id, status, content)
            VALUES ($1::uuid, $2, $3::jsonb)
            ON CONFLICT (concept_id) DO UPDATE SET content = $3::jsonb, updated_at = NOW()
        """, concept_id, status, json.dumps(req.content))
    return {"ok": True}


# ── POST publish — toggle published ──────────────────────────────────────────

@router.post("/{concept_id}/publish")
async def toggle_publish(concept_id: str, authorization: str = Header(...)):
    async with get_db() as db:
        await _assert_teacher(authorization, concept_id, db)
        current = await db.fetchval("SELECT status FROM lab_sheets WHERE concept_id = $1::uuid", concept_id)
        if not current:
            raise HTTPException(404, "No lab sheet exists yet — generate one first")
        new_status = "published" if current == "draft" else "draft"
        await db.execute(
            "UPDATE lab_sheets SET status = $1, updated_at = NOW() WHERE concept_id = $2::uuid",
            new_status, concept_id,
        )
    return {"status": new_status}
