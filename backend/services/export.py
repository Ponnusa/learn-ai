"""
Course export service — HTML and SCORM 1.2 packages.

GET /api/courses/{course_id}/export?format=html   → single .html download
GET /api/courses/{course_id}/export?format=scorm  → SCORM 1.2 .zip download

Data gathered per concept:
  textbook blocks (in_textbook=true), quiz questions (approved),
  flashcards (approved), lab sheet, ai_summary, ai_transcript
"""

import html as _html_mod
import io
import json
import re
import zipfile
from datetime import datetime, timezone

from database import get_db


# ── HTML helpers ─────────────────────────────────────────────────────────────

def _esc(text) -> str:
    return _html_mod.escape(str(text or ""), quote=False)


def _inline_md(text: str) -> str:
    """Bold and italic only. Input must already be HTML-escaped."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__',     r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*\n]+?)\*', r'<em>\1</em>',        text)
    return text


def _content_to_html(text: str) -> str:
    """
    Minimal markdown + LaTeX → HTML.
    Math delimiters ($...$ and $$...$$) are preserved as-is for KaTeX auto-render.
    """
    if not text:
        return ""

    # Protect math from html.escape by replacing with null-byte placeholders
    store: dict[str, str] = {}
    ctr = [0]

    def _save(m: re.Match) -> str:
        k = f"\x00M{ctr[0]}\x00"
        store[k] = m.group(0)
        ctr[0] += 1
        return k

    text = re.sub(r'\$\$[\s\S]*?\$\$', _save, text)   # display math first
    text = re.sub(r'\$[^\$\n]+?\$',    _save, text)   # inline math

    text = _esc(text)  # safe to escape now — math is hidden

    lines = text.split("\n")
    out: list[str] = []
    in_ul = in_ol = False
    para: list[str] = []

    def _flush():
        if para:
            out.append(f"<p>{_inline_md(' '.join(para))}</p>")
            para.clear()

    def _close_list():
        nonlocal in_ul, in_ol
        if in_ul: out.append("</ul>"); in_ul = False
        if in_ol: out.append("</ol>"); in_ol = False

    for ln in lines:
        s = ln.strip()
        if s.startswith("### "):
            _flush(); _close_list()
            out.append(f"<h5>{_inline_md(s[4:])}</h5>")
        elif s.startswith("## "):
            _flush(); _close_list()
            out.append(f"<h4>{_inline_md(s[3:])}</h4>")
        elif s.startswith("# "):
            _flush(); _close_list()
            out.append(f"<h3>{_inline_md(s[2:])}</h3>")
        elif re.match(r'^[-*]\s+', s):
            _flush()
            if not in_ul:
                _close_list(); out.append("<ul>"); in_ul = True
            out.append(f"<li>{_inline_md(re.sub(r'^[-*]\\s+', '', s))}</li>")
        elif re.match(r'^\d+\.\s+', s):
            _flush()
            if not in_ol:
                _close_list(); out.append("<ol>"); in_ol = True
            out.append(f"<li>{_inline_md(re.sub(r'^\\d+\\.\\s+', '', s))}</li>")
        elif not s:
            _flush(); _close_list()
        else:
            if in_ul or in_ol:
                _flush(); _close_list()
            para.append(_inline_md(s))

    _flush(); _close_list()
    result = "\n".join(out)

    # Restore math blocks (placeholders survived html.escape unchanged)
    for k, v in store.items():
        result = result.replace(k, v)

    return result


def _lab_to_html(content: dict) -> str:
    """Render lab sheet JSONB dict as HTML."""
    if not content:
        return "<p><em>No content available.</em></p>"
    parts: list[str] = []

    if content.get("objective"):
        parts.append(f"<h5>Objective</h5><p>{_esc(content['objective'])}</p>")

    if content.get("materials"):
        parts.append("<h5>Materials</h5><ul>")
        parts.extend(f"<li>{_esc(m)}</li>" for m in content["materials"])
        parts.append("</ul>")

    if content.get("safety"):
        parts.append('<h5>⚠️ Safety</h5><ul class="safety">')
        parts.extend(f"<li>{_esc(s)}</li>" for s in content["safety"])
        parts.append("</ul>")

    if content.get("procedure"):
        parts.append("<h5>Procedure</h5><ol>")
        parts.extend(f"<li>{_esc(step)}</li>" for step in content["procedure"])
        parts.append("</ol>")

    dt = content.get("data_table") or {}
    if dt.get("headers"):
        parts.append(f"<h5>{_esc(dt.get('title', 'Data Table'))}</h5>")
        parts.append('<div class="table-wrap"><table><thead><tr>')
        parts.extend(f"<th>{_esc(h)}</th>" for h in dt["headers"])
        parts.append("</tr></thead><tbody>")
        cell_row = "".join("<td>&nbsp;</td>" for _ in dt["headers"])
        parts.extend(f"<tr>{cell_row}</tr>" for _ in range(dt.get("rows", 4)))
        parts.append("</tbody></table></div>")

    if content.get("analysis_questions"):
        parts.append("<h5>Analysis Questions</h5><ol>")
        parts.extend(f"<li>{_esc(q)}</li>" for q in content["analysis_questions"])
        parts.append("</ol>")

    if content.get("conclusion_prompt"):
        parts.append(
            f"<h5>Conclusion</h5><p>{_esc(content['conclusion_prompt'])}</p>"
            '<div class="conclusion-space"></div>'
        )

    return "\n".join(parts)


# ── CSS / JS ──────────────────────────────────────────────────────────────────

_CSS = """
:root{
  --bg:#ffffff;--text:#1a1a2e;--muted:#6b7280;--border:#e5e7eb;
  --surface:#f9fafb;--accent:#4f46e5;--audio-bg:#eff6ff;--warn:#fef9c3;
  --radius:8px;
}
@media(prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#0d1117;--text:#e6edf3;--muted:#8b949e;--border:#30363d;
    --surface:#161b22;--accent:#818cf8;--audio-bg:#1c2333;--warn:#2d2208;
  }
}
:root[data-theme="dark"]{
  --bg:#0d1117;--text:#e6edf3;--muted:#8b949e;--border:#30363d;
  --surface:#161b22;--accent:#818cf8;--audio-bg:#1c2333;--warn:#2d2208;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.7}
.container{max-width:900px;margin:0 auto;padding:2rem 1.5rem 4rem}
.course-header{border-bottom:2px solid var(--accent);padding-bottom:1.25rem;margin-bottom:2rem}
.course-header h1{font-size:1.75rem;color:var(--accent)}
.course-meta{color:var(--muted);font-size:.88rem;margin-top:.4rem}
.course-desc{margin-top:.6rem}
.unit{margin-bottom:2.5rem}
.unit-title{font-size:1.2rem;font-weight:700;padding:.5rem 0;border-bottom:2px solid var(--border);margin-bottom:1rem}
.concept{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:.75rem;overflow:hidden}
.concept-title{font-size:1rem;font-weight:600;padding:.85rem 1.25rem;border-bottom:1px solid var(--border)}
details{border-top:1px solid var(--border)}
summary{padding:.65rem 1.25rem;cursor:pointer;font-weight:600;font-size:.88rem;color:var(--muted);user-select:none;list-style:none;display:flex;align-items:center;gap:.4rem}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸";font-size:.75rem;transition:transform .15s}
details[open] summary::before{content:"▾"}
.section-body{padding:.9rem 1.25rem 1.25rem}
.section-body h3,.section-body h4,.section-body h5{margin:.9rem 0 .35rem;color:var(--accent)}
.section-body p{margin:.4rem 0}
.section-body ul,.section-body ol{padding-left:1.4rem;margin:.4rem 0}
.section-body li{margin:.15rem 0}
.table-wrap{overflow-x:auto;margin:.5rem 0}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{border:1px solid var(--border);padding:.35rem .6rem;text-align:left}
th{background:var(--bg);font-weight:600}
.safety{color:#b45309}
.conclusion-space{border:1px dashed var(--border);height:90px;margin-top:.5rem;border-radius:4px}
.video-link{display:inline-flex;align-items:center;gap:.4rem;padding:.45rem .9rem;background:var(--accent);color:#fff;border-radius:6px;text-decoration:none;font-size:.88rem;margin:.25rem 0}
.video-link:hover{opacity:.85}
.video-block{margin:.4rem 0}
.video-title{font-size:.85rem;color:var(--muted);margin-bottom:.2rem}
audio{width:100%;margin:.35rem 0}
.audio-block{background:var(--audio-bg);padding:.65rem .9rem;border-radius:6px;margin:.4rem 0}
.audio-label{font-size:.8rem;color:var(--muted);margin-bottom:.2rem}
.quiz-item{padding:.9rem 0;border-bottom:1px solid var(--border)}
.quiz-item:last-child{border-bottom:none}
.quiz-q{font-weight:600;margin-bottom:.4rem}
.quiz-opts{list-style:upper-alpha;padding-left:1.4rem;margin:.4rem 0}
.quiz-opts li{margin:.15rem 0}
.quiz-answer{display:none;margin-top:.65rem;padding:.65rem .85rem;background:var(--warn);border-radius:6px;font-size:.9rem}
.quiz-answer.shown{display:block}
.answer-correct{color:#059669;font-weight:700}
.answer-exp{margin-top:.25rem}
.reveal-btn{margin-top:.4rem;padding:.3rem .75rem;border:1px solid var(--accent);border-radius:4px;background:transparent;color:var(--accent);cursor:pointer;font-size:.83rem}
.reveal-btn:hover{background:var(--accent);color:#fff}
.card-grid{display:flex;flex-wrap:wrap;gap:.75rem;margin-top:.5rem}
.flip-card{width:calc(50% - .375rem);cursor:pointer;perspective:800px}
@media(max-width:600px){.flip-card{width:100%}}
.flip-inner{position:relative;width:100%;height:120px;transform-style:preserve-3d;transition:transform .35s}
.flip-card.flipped .flip-inner{transform:rotateY(180deg)}
.flip-front,.flip-back{position:absolute;inset:0;border:1px solid var(--border);border-radius:8px;backface-visibility:hidden;display:flex;align-items:center;justify-content:center;padding:.85rem;text-align:center;font-size:.88rem;overflow:auto}
.flip-front{background:var(--surface)}
.flip-back{background:var(--accent);color:#fff;transform:rotateY(180deg)}
.card-hint{text-align:center;color:var(--muted);font-size:.78rem;margin-top:.2rem}
.transcript-body{white-space:pre-wrap;font-size:.9rem;color:var(--text);line-height:1.8}
.export-footer{text-align:center;color:var(--muted);font-size:.8rem;margin-top:3rem;padding-top:1.25rem;border-top:1px solid var(--border)}
"""

_JS = """
function revealAnswer(btn){
  var item=btn.closest('.quiz-item');
  item.querySelector('.quiz-answer').classList.add('shown');
  btn.style.display='none';
}
document.querySelectorAll('.flip-card').forEach(function(c){
  c.addEventListener('click',function(){this.classList.toggle('flipped');});
});
document.addEventListener('DOMContentLoaded',function(){
  if(typeof renderMathInElement!=='undefined'){
    renderMathInElement(document.body,{
      delimiters:[
        {left:'$$',right:'$$',display:true},
        {left:'$',right:'$',display:false}
      ],
      throwOnError:false
    });
  }
});
"""

_SCORM_JS = """\
(function(){
  function findAPI(w){
    var n=0;
    while(!w.API&&w.parent&&w.parent!==w&&n<7){w=w.parent;n++;}
    return w.API||null;
  }
  var API=null;
  window.addEventListener('load',function(){
    API=findAPI(window);
    if(!API)return;
    API.LMSInitialize('');
    API.LMSSetValue('cmi.core.lesson_status','incomplete');
    API.LMSCommit('');
  });
  window.addEventListener('beforeunload',function(){
    if(!API)return;
    API.LMSSetValue('cmi.core.lesson_status','completed');
    API.LMSFinish('');
  });
})();
"""


# ── Page renderer ─────────────────────────────────────────────────────────────

def _render_concept(c: dict, base_url: str, app_url: str = "") -> str:
    parts = [f'<div class="concept">']
    parts.append(f'<div class="concept-title">📚 {_esc(c["title"])}</div>')

    # ── Textbook blocks ──────────────────────────────────────────────────────
    blocks = c.get("blocks", [])
    text_blocks  = [b for b in blocks if b["type"] == "text"]
    video_blocks = [b for b in blocks if b["type"] == "video" and b.get("video_url")]
    audio_blocks = [b for b in blocks if b.get("has_audio")]

    if text_blocks:
        parts.append('<details open><summary>📖 Textbook</summary><div class="section-body">')
        for b in text_blocks:
            if b.get("title"):
                parts.append(f"<h4>{_esc(b['title'])}</h4>")
            parts.append(_content_to_html(b.get("body") or ""))
        parts.append("</div></details>")

    # ── Video links ──────────────────────────────────────────────────────────
    if video_blocks:
        parts.append('<details><summary>🎬 Video</summary><div class="section-body">')
        for b in video_blocks:
            parts.append('<div class="video-block">')
            if b.get("title"):
                parts.append(f'<div class="video-title">{_esc(b["title"])}</div>')
            # Use in-app watch page so the raw R2 URL is never in the export
            video_id = b.get("video_id")
            if video_id and app_url:
                watch_url = f"{app_url}/watch/{video_id}"
            else:
                watch_url = b.get("video_url", "#")
            parts.append(
                f'<a class="video-link" href="{_esc(watch_url)}" target="_blank">'
                '▶ Watch Video on LearnX AI</a>'
            )
            parts.append("</div>")
        parts.append("</div></details>")

    # ── Audio ────────────────────────────────────────────────────────────────
    if audio_blocks:
        cid = str(c["id"])
        parts.append('<details><summary>🎧 Audio</summary><div class="section-body">')
        for b in audio_blocks:
            bid = b["id"]
            audio_url = f"{base_url}/api/courses/concepts/{cid}/content-blocks/{bid}/audio"
            parts.append('<div class="audio-block">')
            if b.get("title"):
                parts.append(f'<div class="audio-label">{_esc(b["title"])}</div>')
            parts.append(f'<audio controls preload="none"><source src="{_esc(audio_url)}" type="audio/mpeg">Your browser does not support audio.</audio>')
            parts.append("</div>")
        parts.append("</div></details>")

    # ── Transcript ───────────────────────────────────────────────────────────
    if c.get("ai_transcript"):
        parts.append('<details><summary>📝 Transcript</summary><div class="section-body">')
        parts.append(f'<div class="transcript-body">{_esc(c["ai_transcript"])}</div>')
        parts.append("</div></details>")

    # ── Quiz ─────────────────────────────────────────────────────────────────
    quiz = c.get("quiz", [])
    if quiz:
        parts.append(f'<details><summary>❓ Quiz ({len(quiz)} questions)</summary><div class="section-body">')
        for i, q in enumerate(quiz, 1):
            opts = q.get("options") or []
            correct_idx = q.get("correct_idx", 0)
            correct_letter = chr(65 + correct_idx) if 0 <= correct_idx < len(opts) else "?"
            correct_text  = _esc(opts[correct_idx]) if 0 <= correct_idx < len(opts) else ""
            explanation   = _esc(q.get("explanation") or "")

            parts.append('<div class="quiz-item">')
            parts.append(f'<div class="quiz-q">Q{i}. {_esc(q.get("question", ""))}</div>')
            parts.append('<ol class="quiz-opts">')
            for opt in opts:
                parts.append(f"<li>{_esc(opt)}</li>")
            parts.append("</ol>")
            parts.append(
                f'<div class="quiz-answer">'
                f'<div class="answer-correct">✓ {correct_letter}. {correct_text}</div>'
                + (f'<div class="answer-exp">{explanation}</div>' if explanation else "")
                + "</div>"
            )
            parts.append('<button class="reveal-btn" onclick="revealAnswer(this)">Show Answer</button>')
            parts.append("</div>")
        parts.append("</div></details>")

    # ── Flashcards ───────────────────────────────────────────────────────────
    cards = c.get("flashcards", [])
    if cards:
        parts.append(f'<details><summary>🃏 Flashcards ({len(cards)} cards)</summary><div class="section-body">')
        parts.append('<p class="card-hint">Click a card to flip it</p>')
        parts.append('<div class="card-grid">')
        for card in cards:
            parts.append(
                '<div class="flip-card">'
                '<div class="flip-inner">'
                f'<div class="flip-front">{_content_to_html(card.get("front", ""))}</div>'
                f'<div class="flip-back">{_content_to_html(card.get("back", ""))}</div>'
                "</div></div>"
            )
        parts.append("</div></div></details>")

    # ── Lab Sheet ────────────────────────────────────────────────────────────
    lab = c.get("lab_sheet")
    if lab and lab.get("content"):
        content = lab["content"]
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except Exception:
                content = {}
        parts.append('<details><summary>🧪 Lab Sheet</summary><div class="section-body">')
        parts.append(_lab_to_html(content))
        parts.append("</div></details>")

    parts.append("</div>")
    return "\n".join(parts)


def _render_html(data: dict, base_url: str, scorm: bool = False, app_url: str = "") -> str:
    course = data["course"]
    units  = data.get("units", [])
    name   = _esc(course.get("name", "Course Export"))
    desc   = _esc(course.get("description") or "")
    meta_parts = []
    if course.get("subject"): meta_parts.append(_esc(course["subject"]))
    if course.get("grade"):   meta_parts.append(f'Grade {_esc(course["grade"])}')
    if course.get("board"):   meta_parts.append(_esc(course["board"]))
    meta = " · ".join(meta_parts)
    exported = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    scorm_tag = '<script src="scorm_api.js"></script>' if scorm else ""

    units_html_parts = []
    for unit in units:
        concepts_html = "\n".join(
            _render_concept(c, base_url, app_url) for c in unit.get("concepts", [])
        )
        units_html_parts.append(
            f'<div class="unit">'
            f'<div class="unit-title">{_esc(unit["title"])}</div>'
            f"{concepts_html}"
            f"</div>"
        )
    units_html = "\n".join(units_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{name}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" crossorigin="anonymous">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" crossorigin="anonymous"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js" crossorigin="anonymous"></script>
{scorm_tag}
<style>{_CSS}</style>
</head>
<body>
<div class="container">
<header class="course-header">
  <h1>{name}</h1>
  {f'<div class="course-meta">{meta}</div>' if meta else ""}
  {f'<div class="course-desc">{desc}</div>' if desc else ""}
</header>
{units_html}
<footer class="export-footer">Exported from LearnAI · {exported}</footer>
</div>
<script>{_JS}</script>
</body>
</html>"""


def _render_manifest(course_id_safe: str, course_name: str) -> str:
    name_esc = _esc(course_name)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="COURSE_{course_id_safe}" version="1.0"
  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                      http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="{course_id_safe}_org">
    <organization identifier="{course_id_safe}_org">
      <title>{name_esc}</title>
      <item identifier="item_1" identifierref="resource_1">
        <title>{name_esc}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="resource_1" type="webcontent"
              adlcp:scormtype="sco" href="index.html">
      <file href="index.html"/>
      <file href="scorm_api.js"/>
    </resource>
  </resources>
</manifest>"""


# ── Data gathering ────────────────────────────────────────────────────────────

async def gather_course_data(course_id: str) -> dict | None:
    async with get_db() as db:
        course = await db.fetchrow("""
            SELECT name, description, subject, grade, board
            FROM courses WHERE id = $1::uuid
        """, course_id)
        if not course:
            return None

        units = await db.fetch("""
            SELECT id, title, description, position
            FROM course_units WHERE course_id = $1::uuid
            ORDER BY position, created_at
        """, course_id)

        if not units:
            return {"course": dict(course), "units": []}

        unit_ids = [str(u["id"]) for u in units]

        concepts = await db.fetch("""
            SELECT id, unit_id, title, description, ai_summary, ai_transcript, position
            FROM course_concepts
            WHERE unit_id = ANY($1::uuid[])
            ORDER BY unit_id, position, created_at
        """, unit_ids)

        concept_ids = [str(c["id"]) for c in concepts]
        if not concept_ids:
            return {
                "course": dict(course),
                "units": [{"id": str(u["id"]), "title": u["title"],
                           "description": u["description"], "concepts": []} for u in units],
            }

        blocks = await db.fetch("""
            SELECT cb.id::text, cb.concept_id::text, cb.type, cb.position,
                   cb.title, cb.body, cb.audio_status,
                   (cb.audio_data IS NOT NULL) AS has_audio,
                   v.video_url, v.id AS video_id
            FROM concept_content_blocks cb
            LEFT JOIN videos v ON v.id = cb.video_id AND v.status = 'completed'
            WHERE cb.concept_id = ANY($1::uuid[]) AND cb.in_textbook = true
            ORDER BY cb.concept_id, cb.position, cb.created_at
        """, concept_ids)

        quiz_rows = await db.fetch("""
            SELECT concept_id::text, question, options, correct_idx, explanation, position
            FROM concept_quiz_questions
            WHERE concept_id = ANY($1::uuid[]) AND status = 'approved'
            ORDER BY concept_id, position
        """, concept_ids)

        flashcard_rows = await db.fetch("""
            SELECT concept_id::text, front, back, position
            FROM concept_flashcards
            WHERE concept_id = ANY($1::uuid[]) AND status = 'approved'
            ORDER BY concept_id, position
        """, concept_ids)

        lab_rows = await db.fetch("""
            SELECT concept_id::text, content, status
            FROM lab_sheets
            WHERE concept_id = ANY($1::uuid[])
        """, concept_ids)

    # Index by concept
    blocks_map:    dict[str, list] = {}
    quiz_map:      dict[str, list] = {}
    flashcard_map: dict[str, list] = {}
    lab_map:       dict[str, dict] = {}

    for b in blocks:
        blocks_map.setdefault(b["concept_id"], []).append(dict(b))

    for q in quiz_rows:
        opts = q["options"]
        if isinstance(opts, str):
            opts = json.loads(opts)
        quiz_map.setdefault(q["concept_id"], []).append({
            "question":    q["question"],
            "options":     opts,
            "correct_idx": q["correct_idx"],
            "explanation": q["explanation"],
        })

    for f in flashcard_rows:
        flashcard_map.setdefault(f["concept_id"], []).append({"front": f["front"], "back": f["back"]})

    for l in lab_rows:
        lab_map[l["concept_id"]] = {"content": l["content"], "status": l["status"]}

    # Group concepts by unit
    concept_map: dict[str, list] = {}
    for c in concepts:
        cid = str(c["id"])
        uid = str(c["unit_id"])
        concept_map.setdefault(uid, []).append({
            "id":            cid,
            "title":         c["title"],
            "description":   c["description"],
            "ai_summary":    c["ai_summary"],
            "ai_transcript": c["ai_transcript"],
            "blocks":        blocks_map.get(cid, []),
            "quiz":          quiz_map.get(cid, []),
            "flashcards":    flashcard_map.get(cid, []),
            "lab_sheet":     lab_map.get(cid),
        })

    return {
        "course": dict(course),
        "units": [
            {
                "id":          str(u["id"]),
                "title":       u["title"],
                "description": u["description"],
                "concepts":    concept_map.get(str(u["id"]), []),
            }
            for u in units
        ],
    }


# ── Public API ────────────────────────────────────────────────────────────────

async def export_html(course_id: str, base_url: str, app_url: str = "") -> bytes:
    data = await gather_course_data(course_id)
    if data is None:
        return None
    return _render_html(data, base_url, scorm=False, app_url=app_url).encode("utf-8")


async def export_scorm(course_id: str, base_url: str, app_url: str = "") -> bytes:
    data = await gather_course_data(course_id)
    if data is None:
        return None

    html_bytes  = _render_html(data, base_url, scorm=True, app_url=app_url).encode("utf-8")
    course_name = data["course"]["name"]
    safe_id     = course_id.replace("-", "")
    manifest    = _render_manifest(safe_id, course_name).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("imsmanifest.xml", manifest)
        zf.writestr("scorm_api.js",    _SCORM_JS.encode("utf-8"))
        zf.writestr("index.html",      html_bytes)
    return buf.getvalue()
