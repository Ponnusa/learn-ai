"""
Educational Image Generator — core pipeline.

Flow:
  1. Keyword-classify domain (physics / chemistry / biology / etc.)
  2. Claude → structured educational image spec (JSON)
  3. Spec → standardised OpenAI image prompt
  4. DALL-E 3 → temporary image URL
  5. Download + upload to R2 for permanent storage
  6. Update DB job record
"""
import json
import logging
import httpx

logger = logging.getLogger(__name__)

# ── Domain rules — drive Claude spec + prompt emphasis ────────────────────────

DOMAIN_RULES: dict[str, dict] = {
    "physics": {
        "emphasis": [
            "force vectors", "velocity/acceleration arrows", "field lines",
            "energy level diagrams", "free-body diagrams", "wave crests",
        ],
        "style": "clean physics textbook diagram with labelled vectors and force arrows",
    },
    "chemistry": {
        "emphasis": [
            "molecular structures", "reaction arrow mechanisms", "apparatus cross-sections",
            "electron orbitals", "bond angles", "periodic table elements",
        ],
        "style": "chemistry textbook diagram with accurate molecular representations and reaction arrows",
    },
    "mathematics": {
        "emphasis": [
            "labelled coordinate axes", "geometric shapes with dimensions",
            "function graphs", "proof steps", "angles and measurements",
        ],
        "style": "precise mathematical diagram with exact labels, grids, and annotated variables",
    },
    "biology": {
        "emphasis": [
            "labelled anatomical structures", "cellular organelles", "process arrows",
            "magnification callouts", "colour-coded regions",
        ],
        "style": "biology textbook illustration with detailed labelled structures and process flow",
    },
    "geography": {
        "emphasis": [
            "geographical features", "directional arrows", "scale reference",
            "climate zones", "physical process labels",
        ],
        "style": "geography textbook diagram with labelled features, legend, and directional indicators",
    },
    "general": {
        "emphasis": [
            "key components", "numbered steps", "cause-effect arrows",
            "labelled sections", "logical flow",
        ],
        "style": "clean educational infographic with clear labels and logical flow",
    },
}

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "physics":     ["force", "velocity", "acceleration", "momentum", "energy", "wave",
                    "gravity", "electric", "magnetic", "quantum", "thermodynamics",
                    "optics", "Newton", "friction", "inclined", "pulley", "circuit"],
    "chemistry":   ["molecule", "atom", "bond", "reaction", "element", "compound",
                    "periodic", "acid", "base", "organic", "electron", "titration",
                    "polymer", "covalent", "ionic", "oxidation"],
    "mathematics": ["equation", "graph", "function", "derivative", "integral",
                    "geometry", "algebra", "triangle", "circle", "probability",
                    "matrix", "vector", "polynomial", "calculus", "logarithm"],
    "biology":     ["cell", "DNA", "protein", "organism", "evolution", "photosynthesis",
                    "neuron", "enzyme", "gene", "mitosis", "chlorophyll", "diffusion",
                    "osmosis", "chromosome", "respiration"],
    "geography":   ["climate", "plate", "tectonic", "continent", "ocean", "watershed",
                    "biome", "atmosphere", "volcanic", "erosion", "glacier", "river",
                    "latitude", "longitude"],
}


def classify_domain(concept: str) -> str:
    """Fast keyword-based domain classification."""
    c = concept.lower()
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(kw.lower() in c for kw in kws):
            return domain
    return "general"


async def generate_spec_via_claude(concept: str, domain: str) -> dict:
    """Call Claude Haiku to convert the user concept into a structured image spec."""
    from anthropic import AsyncAnthropic

    rules = DOMAIN_RULES.get(domain, DOMAIN_RULES["general"])

    system = (
        "You are an expert educational illustrator who creates precise specifications "
        "for educational diagrams. Output valid JSON only — no markdown fences, no extra text."
    )
    user = f"""Create an educational image specification for:
"{concept}"

Domain: {domain}
Key elements to emphasise: {", ".join(rules["emphasis"][:4])}

Return a JSON object with exactly these keys:
{{
  "domain": "{domain}",
  "title": "max 8-word descriptive title",
  "subject": "main subject of the diagram",
  "visual_elements": ["3 to 8 specific visual elements"],
  "labels": true,
  "background": "white",
  "style": "{rules['style']}",
  "difficulty": "high school",
  "key_relationships": "one sentence describing the main process or relationship shown"
}}

Be specific: instead of "forces", write "gravity vector pointing straight down" and "normal force vector perpendicular to surface"."""

    client = AsyncAnthropic()
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    raw = response.content[0].text.strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1][4:].strip() if parts[1].startswith("json") else parts[1].strip()
    return json.loads(raw)


def build_image_prompt(spec: dict, domain: str) -> str:
    """Convert a structured spec into a final DALL-E image generation prompt."""
    rules = DOMAIN_RULES.get(domain, DOMAIN_RULES["general"])
    elements = "\n".join(f"- {e}" for e in spec.get("visual_elements", []))
    key_rel = spec.get("key_relationships", "")

    return f"""Educational {domain} diagram for students.

Topic: {spec.get("title", spec.get("subject", "Educational concept"))}.
{key_rel}

Include:
{elements}

Requirements:
- clean, professional textbook illustration
- pure white background
- all elements clearly and concisely labelled
- {rules["style"]}
- high educational clarity — easy to read and understand
- suitable for high school students

Avoid:
- artistic or decorative styles
- photorealistic rendering
- decorative or gradient backgrounds
- excessive decorative detail
- cluttered overlapping labels"""


async def generate_image_openai(prompt: str) -> str:
    """Generate image via DALL-E 3; returns the (temporary) OpenAI URL."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url


async def store_image_r2(image_url: str, job_id: str, user_id: str | None, session_id: str | None) -> str:
    """Download from OpenAI (temporary URL) and store permanently in R2."""
    from services.manim import _make_r2_client, R2_BUCKET_NAME, R2_PUBLIC_URL

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(image_url)
        if r.status_code != 200:
            raise RuntimeError(f"Failed to download generated image: HTTP {r.status_code}")
        data = r.content

    if user_id:
        key = f"educational-images/{user_id}/{job_id}.png"
    elif session_id:
        key = f"educational-images/anon/{session_id}/{job_id}.png"
    else:
        key = f"educational-images/public/{job_id}.png"

    r2 = _make_r2_client()
    if not r2:
        raise RuntimeError("R2 storage not configured — cannot store image")

    r2.put_object(Bucket=R2_BUCKET_NAME, Key=key, Body=data, ContentType="image/png")
    logger.info("[edu-img] stored %s (%d bytes)", key, len(data))
    return f"{R2_PUBLIC_URL.rstrip('/')}/{key}"


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def process_image_job(job_id: str, concept: str, user_id: str | None, session_id: str | None) -> None:
    """
    Full async pipeline — runs as a FastAPI BackgroundTask.
    Status transitions: processing → ready | failed
    """
    from database import get_db

    try:
        # 1. Domain
        domain = classify_domain(concept)
        logger.info("[edu-img] %s domain=%s", job_id[:8], domain)

        # 2. Spec via Claude
        spec = await generate_spec_via_claude(concept, domain)
        logger.info("[edu-img] %s spec=%s", job_id[:8], spec.get("title"))

        # Persist domain + spec early so polling can show progress
        async with get_db() as db:
            await db.execute(
                "UPDATE educational_images SET domain=$1, spec=$2::jsonb WHERE id=$3::uuid",
                domain, json.dumps(spec), job_id,
            )

        # 3. Build prompt
        prompt = build_image_prompt(spec, domain)

        # 4. Generate via DALL-E 3
        temp_url = await generate_image_openai(prompt)
        logger.info("[edu-img] %s image generated", job_id[:8])

        # 5. Store in R2
        r2_url = await store_image_r2(temp_url, job_id, user_id, session_id)

        # 6. Mark ready
        async with get_db() as db:
            await db.execute(
                """UPDATE educational_images
                   SET status='ready', image_url=$1, prompt=$2
                   WHERE id=$3::uuid""",
                r2_url, prompt, job_id,
            )
        logger.info("[edu-img] %s ready → %s", job_id[:8], r2_url)

    except Exception as exc:
        logger.exception("[edu-img] %s failed: %s", job_id[:8], exc)
        from database import get_db as _get_db
        async with _get_db() as db:
            await db.execute(
                "UPDATE educational_images SET status='failed', error_msg=$1 WHERE id=$2::uuid",
                str(exc)[:500], job_id,
            )
