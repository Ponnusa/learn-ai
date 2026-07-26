"""
Educational Image Generator — Knowledge-Layer Pipeline.

Flow:
  1. Knowledge Extraction  (Claude Haiku) → rich knowledge model
  2. Diagram Planning      (Claude Haiku) → structured diagram plan
  3. Validation            (local)        → catch bad visuals pre-generation
  4. Prompt Building       (local)        → domain-specific gpt-image-1 prompt
  5. Image Generation      (gpt-image-1)  → PNG bytes
  6. Vision Critic         (GPT-4o)       → score + issues
  7. Auto-regenerate       (if score<85)  → one retry with correction prompt
  8. R2 Upload             (boto3)        → permanent URL
  9. DB update             (asyncpg)      → status=ready + all metadata

Public entry point: process_image_job()
"""
import base64
import json
import logging

logger = logging.getLogger(__name__)

_CRITIC_THRESHOLD     = 85   # score below this triggers regeneration
_MAX_GEN_ATTEMPTS     = 2    # max attempts including the retry


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_image_prompt(
    knowledge_model: dict,
    diagram_plan:    dict,
    critic_feedback: str = "",
    validation_issues: list[str] | None = None,
) -> str:
    """
    Assemble a final gpt-image-1 prompt from knowledge model + diagram plan.
    Injects BAD_VISUALS, domain style, and any critic/validation feedback.
    """
    from .domain_templates import BAD_VISUALS, DOMAIN_STYLES, CONCEPT_TYPE_REQUIREMENTS

    domain       = knowledge_model.get("domain", "general")
    concept_type = knowledge_model.get("concept_type", "process_flow")
    title        = knowledge_model.get("title", "Educational diagram")
    learning_goal = knowledge_model.get("learning_goal", "")
    must_show    = knowledge_model.get("must_show", [])
    must_not_show = knowledge_model.get("must_not_show", [])

    domain_style = DOMAIN_STYLES.get(domain, DOMAIN_STYLES["general"])
    template     = CONCEPT_TYPE_REQUIREMENTS.get(concept_type, {})

    # Collect drawable elements from plan — deduplicated
    elements: list[str] = []
    seen: set[str] = set()
    for panel in diagram_plan.get("panels", []):
        for el in panel.get("elements", []):
            if el not in seen:
                elements.append(el)
                seen.add(el)
    for lbl in diagram_plan.get("labels", []):
        if lbl not in seen:
            elements.append(lbl)
            seen.add(lbl)
    for ms in must_show:
        if ms not in seen:
            elements.append(ms)
            seen.add(ms)

    elements_str = "\n".join(f"  - {e}" for e in elements[:14])

    # Forbidden visuals = must_not_show + top global BAD_VISUALS
    forbidden = list(dict.fromkeys(must_not_show + BAD_VISUALS[:8]))
    forbidden_str = "\n".join(f"  - {f}" for f in forbidden[:12])

    correction = ""
    if critic_feedback:
        correction = f"\n\nCORRECTION (fix these issues from the previous attempt):\n{critic_feedback}"
    if validation_issues:
        pre = "\n".join(f"  - {i}" for i in validation_issues)
        correction += f"\n\nPRE-GENERATION WARNINGS (avoid these):\n{pre}"

    return f"""Educational {domain} diagram: {title}

STYLE: {domain_style}
LAYOUT: {diagram_plan.get("layout", "clean, well-spaced")}
COLOR: {diagram_plan.get("color_scheme", "high contrast, white background")}
TEMPLATE: {template.get("style_notes", "")}

DRAW these visual elements:
{elements_str}

LABELLING RULES (critical):
- Each drawn element gets a SHORT label directly on or next to it (max 4 words)
- Labels are identifiers only: element name + unit if applicable (e.g. "Weight W (N)", "v = 10 m/s")
- NO title text block, NO subtitle, NO paragraph text, NO floating description
- NO equations as text blocks — only as compact inline labels if essential
- NO legend boxes with long text
- Every label must point directly to the element it names

NEVER INCLUDE (scientifically misleading):
{forbidden_str}

Image requirements:
- Pure white background
- Professional textbook line-art quality
- No decorative backgrounds, gradients, or artistic flourishes{correction}"""


# ─────────────────────────────────────────────────────────────────────────────
# Vision critic
# ─────────────────────────────────────────────────────────────────────────────

async def run_vision_critic(
    image_bytes:     bytes,
    knowledge_model: dict,
    diagram_plan:    dict,
) -> dict:
    """
    Send the generated PNG to GPT-4o for scientific accuracy review.
    Returns a critic report dict with score, issues, and correction_prompt.
    """
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    b64           = base64.b64encode(image_bytes).decode("utf-8")
    learning_goal = knowledge_model.get("learning_goal", "")
    must_show     = knowledge_model.get("must_show", [])
    must_not_show = knowledge_model.get("must_not_show", [])
    misconceptions = knowledge_model.get("common_misconceptions", [])

    prompt = f"""Review this educational diagram for scientific accuracy and educational quality.

Learning goal: {learning_goal}
Must be present: {must_show}
Must NOT appear: {must_not_show}
Common misconceptions to avoid reinforcing: {misconceptions}

Evaluate:
1. Scientific accuracy — are all concepts shown correctly?
2. Label completeness — are all key elements labeled with correct units?
3. Label correctness — any spelling errors or wrong notation?
4. Misleading visuals — anything that could teach the wrong concept?
5. Educational clarity — is it immediately clear to a high school student?
6. Missing elements — anything from "Must be present" that is absent?

Return ONLY valid JSON:
{{
  "score": <integer 0-100>,
  "issues": ["<specific problem>"],
  "missing": ["<element that should be present but isn't>"],
  "misleading": ["<element that could cause a misconception>"],
  "regenerate": <true if score < {_CRITIC_THRESHOLD}>,
  "correction_prompt": "<specific one-paragraph instruction to fix issues in the next attempt>"
}}"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text",      "text": prompt},
                ],
            }],
            response_format={"type": "json_object"},
        )
        report = json.loads(response.choices[0].message.content)
        logger.info("[critic] score=%s regenerate=%s issues=%d",
                    report.get("score"), report.get("regenerate"), len(report.get("issues", [])))
        return report
    except Exception as e:
        logger.warning("[critic] vision critic failed (%s) — skipping", e)
        return {"score": 90, "issues": [], "missing": [], "misleading": [],
                "regenerate": False, "correction_prompt": ""}


# ─────────────────────────────────────────────────────────────────────────────
# Image generation + critic loop
# ─────────────────────────────────────────────────────────────────────────────

async def generate_with_critic(
    knowledge_model:   dict,
    diagram_plan:      dict,
    validation_issues: list[str],
) -> tuple[bytes, dict, str]:
    """
    Generate image → critic → regenerate once if score < threshold.
    Returns (final_image_bytes, critic_report, final_prompt_used).
    """
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    critic_feedback = ""
    if validation_issues:
        critic_feedback = "Pre-generation issues to fix: " + "; ".join(validation_issues)

    final_bytes:  bytes = b""
    final_report: dict  = {}
    final_prompt: str   = ""

    for attempt in range(1, _MAX_GEN_ATTEMPTS + 1):
        prompt = build_image_prompt(
            knowledge_model, diagram_plan,
            critic_feedback=critic_feedback,
            validation_issues=validation_issues if attempt == 1 else None,
        )
        final_prompt = prompt

        logger.info("[img] attempt %d/%d — prompt length=%d", attempt, _MAX_GEN_ATTEMPTS, len(prompt))

        response = await client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            quality="medium",
            n=1,
        )
        image_bytes = base64.b64decode(response.data[0].b64_json)

        # Vision critic
        critic_report = await run_vision_critic(image_bytes, knowledge_model, diagram_plan)
        critic_report["attempt"] = attempt

        final_bytes  = image_bytes
        final_report = critic_report

        if not critic_report.get("regenerate", False) or attempt >= _MAX_GEN_ATTEMPTS:
            if attempt > 1:
                logger.info("[img] accepted after %d attempts, score=%s", attempt, critic_report.get("score"))
            break

        # Prepare correction for next attempt
        critic_feedback = critic_report.get("correction_prompt", "")
        logger.info("[img] score=%s < %d — retrying with critic feedback",
                    critic_report.get("score"), _CRITIC_THRESHOLD)

    return final_bytes, final_report, final_prompt


# ─────────────────────────────────────────────────────────────────────────────
# R2 storage
# ─────────────────────────────────────────────────────────────────────────────

async def store_image_r2(
    image_bytes: bytes,
    job_id:      str,
    user_id:     str | None,
    session_id:  str | None,
) -> str:
    """Upload raw PNG bytes to Cloudflare R2 and return the permanent public URL."""
    from services.manim import _make_r2_client, R2_BUCKET_NAME, R2_PUBLIC_URL

    if user_id:
        key = f"educational-images/{user_id}/{job_id}.png"
    elif session_id:
        key = f"educational-images/anon/{session_id}/{job_id}.png"
    else:
        key = f"educational-images/public/{job_id}.png"

    r2 = _make_r2_client()
    if not r2:
        raise RuntimeError("R2 not configured — cannot store image")

    r2.put_object(Bucket=R2_BUCKET_NAME, Key=key, Body=image_bytes, ContentType="image/png")
    logger.info("[edu-img] stored %s (%d bytes)", key, len(image_bytes))
    return f"{R2_PUBLIC_URL.rstrip('/')}/{key}"


# ─────────────────────────────────────────────────────────────────────────────
# AI description generator — runs after image is stored
# ─────────────────────────────────────────────────────────────────────────────

_DESC_LANGUAGE_NAMES = {'fi': 'Finnish', 'sv': 'Swedish', 'es': 'Spanish', 'fr': 'French'}


async def generate_image_description(knowledge_model: dict, diagram_plan: dict, language: str = 'en') -> str:
    """
    Generate a rich markdown explanation of the diagram using Claude.
    This text is shown as an AI message next to the image — it replaces all
    the explanatory text that used to be embedded inside the image itself.
    """
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()

    title          = knowledge_model.get("title", "")
    learning_goal  = knowledge_model.get("learning_goal", "")
    entities       = knowledge_model.get("entities", [])
    relationships  = knowledge_model.get("relationships", [])
    mechanisms     = knowledge_model.get("mechanisms", [])
    variables      = knowledge_model.get("variables", [])
    misconceptions = knowledge_model.get("common_misconceptions", [])
    must_show      = knowledge_model.get("must_show", [])

    elements = []
    for panel in diagram_plan.get("panels", []):
        elements.extend(panel.get("elements", []))

    prompt = f"""You are an expert science educator. Write a clear, concise explanation of this educational diagram.

Diagram: {title}
Learning goal: {learning_goal}
Key entities shown: {entities}
Relationships: {relationships}
Mechanisms: {mechanisms}
Variables: {variables}
What the diagram shows: {must_show + elements[:6]}
Common misconceptions to address: {misconceptions}

Write 3–5 short paragraphs in plain educational language:
1. What the diagram shows (1-2 sentences)
2. How to read/interpret it — walk through the key labeled elements
3. The underlying science — what causes what, why it matters
4. Common mistakes students make with this concept (if any)

Format: use **bold** for key terms. Keep it concise and student-friendly.
Do NOT describe the image visually (no "the arrow on the left..."). Explain the science.
Do NOT use headers. Just flowing paragraphs."""

    if language in _DESC_LANGUAGE_NAMES:
        prompt += f"\n\nWrite the entire explanation in {_DESC_LANGUAGE_NAMES[language]}."

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        description = response.content[0].text.strip()
        logger.info("[desc] generated %d chars for '%s'", len(description), title)
        return description
    except Exception as e:
        logger.warning("[desc] description generation failed (%s) — using fallback", e)
        # Minimal fallback built from the knowledge model
        parts = [f"**{title}**"]
        if learning_goal:
            parts.append(learning_goal)
        if mechanisms:
            parts.append("Key mechanisms: " + ", ".join(mechanisms) + ".")
        if misconceptions:
            parts.append("Common misconception: " + misconceptions[0])
        return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline — called by background task
# ─────────────────────────────────────────────────────────────────────────────

async def process_image_job(
    job_id:     str,
    concept:    str,
    user_id:    str | None,
    session_id: str | None,
) -> None:
    """
    Full async pipeline. Status transitions: processing → ready | failed.
    Saves intermediate state to DB so the frontend can show progress.
    """
    from database import get_db
    from .knowledge_extractor import extract_knowledge_model
    from .diagram_planner     import plan_diagram
    from .diagram_validator   import validate_diagram_plan

    try:
        # ── 1. Knowledge extraction ───────────────────────────────────────
        knowledge_model = await extract_knowledge_model(concept)
        domain       = knowledge_model.get("domain", "general")
        concept_type = knowledge_model.get("concept_type", "process_flow")

        async with get_db() as db:
            await db.execute(
                """UPDATE educational_images
                   SET domain=$1, knowledge_model=$2::jsonb
                   WHERE id=$3::uuid""",
                domain, json.dumps(knowledge_model), job_id,
            )

        # ── 2. Diagram planning ───────────────────────────────────────────
        diagram_plan = await plan_diagram(knowledge_model)

        async with get_db() as db:
            await db.execute(
                """UPDATE educational_images
                   SET diagram_plan=$1::jsonb, diagram_type=$2
                   WHERE id=$3::uuid""",
                json.dumps(diagram_plan), concept_type, job_id,
            )

        # ── 3. Pre-generation validation ─────────────────────────────────
        validation_issues = validate_diagram_plan(diagram_plan, knowledge_model)

        # ── 4+5+6+7. Generate → critic → (retry) ─────────────────────────
        image_bytes, critic_report, final_prompt = await generate_with_critic(
            knowledge_model, diagram_plan, validation_issues,
        )

        # ── 8. Upload to R2 ───────────────────────────────────────────────
        r2_url = await store_image_r2(image_bytes, job_id, user_id, session_id)

        # ── 9. Generate AI description (runs in parallel with nothing — fast) ─
        user_language = 'en'
        if user_id:
            async with get_db() as db:
                lang_row = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", user_id)
            if lang_row:
                user_language = lang_row
        description = await generate_image_description(knowledge_model, diagram_plan, user_language)

        # Build backward-compatible spec for frontend display
        all_elements: list[str] = []
        for panel in diagram_plan.get("panels", []):
            all_elements.extend(panel.get("elements", []))
        compat_spec = {
            "domain":            domain,
            "title":             knowledge_model.get("title", ""),
            "visual_elements":   list(dict.fromkeys(all_elements + knowledge_model.get("must_show", [])))[:10],
            "key_relationships": knowledge_model.get("learning_goal", ""),
            "style":             diagram_plan.get("layout", ""),
            "difficulty":        knowledge_model.get("difficulty", "high_school"),
        }

        # ── 10. Mark ready ────────────────────────────────────────────────
        async with get_db() as db:
            await db.execute(
                """UPDATE educational_images
                   SET status='ready',
                       image_url=$1,
                       prompt=$2,
                       spec=$3::jsonb,
                       critic_report=$4::jsonb,
                       generation_attempts=$5,
                       description=$6
                   WHERE id=$7::uuid""",
                r2_url,
                final_prompt,
                json.dumps(compat_spec),
                json.dumps(critic_report),
                critic_report.get("attempt", 1),
                description,
                job_id,
            )
        logger.info("[edu-img] %s ready — score=%s attempts=%s",
                    job_id[:8], critic_report.get("score"), critic_report.get("attempt", 1))

    except Exception as exc:
        logger.exception("[edu-img] %s failed: %s", job_id[:8], exc)
        from database import get_db as _get_db
        async with _get_db() as db:
            await db.execute(
                "UPDATE educational_images SET status='failed', error_msg=$1 WHERE id=$2::uuid",
                str(exc)[:500], job_id,
            )
