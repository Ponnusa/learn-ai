"""
Seed TEKS Science standards from the SelahLearn/texasteks HuggingFace dataset.

Run once against Neon:
  cd backend && python scripts/seed_teks.py

What it does:
  1. Creates the standards table if not exists
  2. Downloads science.json from HuggingFace
  3. Converts CASE codes (112.26.b.6.A) → short codes (6.6A)
  4. Inserts all records (upsert — safe to re-run)
  5. Validates existing curriculum_contexts teks_codes against the table
"""
import asyncio
import json
import re
import sys
import urllib.request
from pathlib import Path

DATABASE_URL = "postgresql://neondb_owner:npg_5FMjA6CmzfYZ@ep-mute-field-agoe6wsn-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
JSON_URL     = "https://huggingface.co/datasets/SelahLearn/texasteks/raw/main/data/science.json"

# CASE course number → grade label (Science only)
_CASE_TO_GRADE = {
    "112.2":  "K",
    "112.3":  "1",
    "112.4":  "2",
    "112.5":  "3",
    "112.6":  "4",
    "112.7":  "5",
    "112.26": "6",
    "112.27": "7",
    "112.28": "8",
    "112.39": "HS",   # Biology
    "112.40": "HS",   # Chemistry
    "112.41": "HS",   # Physics
    "112.42": "HS",   # Earth Science
    "112.43": "HS",   # Environmental Systems
}

# Regex: captures (course_num).(section).(sub_letter) from a CASE code
# e.g. "112.26.b.6.A"  → course=112.26, section=6, sub=A
# e.g. "112.26.b.6"    → course=112.26, section=6, sub=None
_CODE_RE = re.compile(
    r"^(\d+\.\d+)\.b\.(\d+)(?:\.([A-Z]))?",
    re.IGNORECASE,
)


def case_to_short(case_code: str, grade_level: str) -> str | None:
    """
    Convert a CASE code to the short form used in curriculum_contexts.teks_codes.

    112.26.b.6.A  + grade 6  →  6.6A
    112.26.b.8.B  + grade 6  →  6.8B
    112.26.b.6    + grade 6  →  6.6   (strand level — no letter)
    """
    m = _CODE_RE.match(case_code)
    if not m:
        return None
    course_num, section, sub = m.group(1), m.group(2), m.group(3)
    grade = _CASE_TO_GRADE.get(course_num, grade_level)
    if sub:
        return f"{grade}.{section}{sub.upper()}"
    return f"{grade}.{section}"


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS standards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board       TEXT NOT NULL DEFAULT 'TEKS',
    state       TEXT NOT NULL DEFAULT 'TX',
    grade       TEXT NOT NULL,
    subject     TEXT NOT NULL DEFAULT 'Science',
    case_code   TEXT NOT NULL,          -- e.g. 112.26.b.6.A
    short_code  TEXT,                   -- e.g. 6.6A  (null for strand-level)
    title       TEXT NOT NULL,
    description TEXT,
    sort_order  INT,
    teks_uuid   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (board, case_code)
);
CREATE INDEX IF NOT EXISTS idx_standards_short_code ON standards (short_code);
CREATE INDEX IF NOT EXISTS idx_standards_grade      ON standards (grade);
"""


async def main():
    import asyncpg

    # ── 1. Download JSON ──────────────────────────────────────────────────────
    print(f"Fetching {JSON_URL} ...")
    local_path = Path(__file__).parent / "_teks_science.json"
    if local_path.exists():
        print("  (using cached local copy)")
        data = json.loads(local_path.read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(JSON_URL, timeout=60) as resp:
            raw = resp.read()
        local_path.write_bytes(raw)
        data = json.loads(raw)
    print(f"  {len(data)} records loaded")

    # ── 2. Connect ────────────────────────────────────────────────────────────
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(CREATE_TABLE)
    print("  standards table ready")

    # ── 3. Upsert ─────────────────────────────────────────────────────────────
    inserted = skipped = 0
    for rec in data:
        case_code   = rec.get("code", "").strip()
        grade_level = str(rec.get("grade_level", "")).strip()
        title       = (rec.get("title") or "").strip()
        if not case_code or not title:
            skipped += 1
            continue

        short_code = case_to_short(case_code, grade_level)

        await conn.execute("""
            INSERT INTO standards (board, state, grade, subject, case_code, short_code, title, description, sort_order, teks_uuid)
            VALUES ('TEKS', 'TX', $1, 'Science', $2, $3, $4, $5, $6, $7)
            ON CONFLICT (board, case_code) DO UPDATE
                SET title      = EXCLUDED.title,
                    short_code = EXCLUDED.short_code,
                    grade      = EXCLUDED.grade
        """,
            grade_level,
            case_code,
            short_code,
            title,
            rec.get("description"),
            rec.get("sort_order"),
            rec.get("teks_uuid"),
        )
        inserted += 1

    print(f"  {inserted} records upserted, {skipped} skipped")

    # ── 4. Validate existing curriculum_contexts codes ────────────────────────
    print()
    print("=== Validating curriculum_contexts TEKS codes ===")
    ctx_rows = await conn.fetch(
        "SELECT id, name, teks_codes FROM curriculum_contexts WHERE teks_codes IS NOT NULL"
    )
    for ctx in ctx_rows:
        print(f"\n  Unit: {ctx['name']}")
        codes = ctx["teks_codes"] or []
        for code in codes:
            match = await conn.fetchrow(
                "SELECT case_code, title FROM standards WHERE short_code = $1 AND board = 'TEKS'",
                code,
            )
            if match:
                # Truncate long titles for display
                preview = match["title"][:90] + "..." if len(match["title"]) > 90 else match["title"]
                print(f"    OK {code:6s}  ({match['case_code']})  {preview}")
            else:
                print(f"    XX {code:6s}  NOT FOUND in standards table")

    # ── 5. Show all grade 6 standards for reference ───────────────────────────
    print()
    print("=== All Grade 6 Science standards in table ===")
    g6 = await conn.fetch(
        "SELECT short_code, case_code, title FROM standards WHERE grade = '6' ORDER BY sort_order",
    )
    for r in g6:
        short = r["short_code"] or "     "
        preview = r["title"][:80] + "..." if len(r["title"]) > 80 else r["title"]
        print(f"  {short:8s} ({r['case_code']:16s})  {preview}")

    await conn.close()
    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
