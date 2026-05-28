"""
Manim video generation pipeline — copied verbatim from AnimLearn main.py.
AnimLearn is the source of truth for all prompts and pipeline logic.
When a prompt is improved in AnimLearn, sync it here.

Public API (imported by routers/videos.py):
  generate_manim_code_enhanced(prompt, language, duration, aspect_ratio) → async dict
  generate_solution_only(prompt, language, duration)                      → async dict
  generate_manim_from_solution(solution_data, language, duration, ar)    → async dict
  fix_manim_colors(code)       → str
  ensure_numpy_import(code)    → str
  _trigger_video_generation(video_id, svg_urls) → None (fire-and-forget)
"""
import ast as _ast_module
import os
import re
import json
import time
import logging
import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config
import anthropic
import openai as _openai_module
import requests

from config import settings

logger = logging.getLogger(__name__)

# ── Synchronous AI clients (Manim pipeline is CPU/IO-bound, runs via asyncio.to_thread) ─
# Timeout: 120 s per request so hung calls fail fast and surface as 'failed'
# rather than keeping the video stuck at 'transcript_ready' for 10+ minutes.
_claude_sync = anthropic.Anthropic(
    api_key=settings.ANTHROPIC_API_KEY,
    timeout=120.0,
)
_openai_sync = _openai_module.OpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=120.0,
)

# ── Model for Manim code generation (same tier as AnimLearn) ─────────────────────────
_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL_NAME", "claude-opus-4-7")

# ── R2 / Cloudflare config (mirrors AnimLearn naming for verbatim function copy) ──────
R2_BUCKET_NAME = settings.R2_BUCKET_NAME
R2_PUBLIC_URL  = settings.R2_PUBLIC_URL

def _make_r2_client():
    """Create R2 client — returns None (silently) if R2 is not configured or config is invalid."""
    account_id = settings.R2_ACCOUNT_ID
    if not account_id:
        return None
    # Cloudflare account IDs are 32-char hex strings — reject anything that
    # looks like a key/secret accidentally pasted into the wrong env var.
    import re as _re
    if not _re.fullmatch(r'[a-fA-F0-9]{32}', account_id):
        logger.warning(
            "⚠️  R2_ACCOUNT_ID looks invalid (expected 32-char hex). "
            "SVG asset caching disabled. Check your Railway env vars."
        )
        return None
    try:
        return boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    except Exception as e:
        logger.warning(f"⚠️  Could not create R2 client — SVG caching disabled: {e}")
        return None

r2_client = _make_r2_client()

# ── Cloud Run trigger config ──────────────────────────────────────────────────────────
CLOUD_RUN_URL      = settings.CLOUD_RUN_VIDEO_URL
RAILWAY_CALL_TOKEN = settings.CLOUD_RUN_SECRET

# ─────────────────────────────────────────────────────────────────────────────────────
# RETRY WRAPPER
# ─────────────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────────────
# AST UNDEFINED-NAME CHECKER
# Catches variables used in animations that were never assigned — the #1 crash cause.
# ─────────────────────────────────────────────────────────────────────────────────────

_MANIM_GLOBALS: frozenset = frozenset({
    # directions
    'UP','DOWN','LEFT','RIGHT','ORIGIN','IN','OUT','UR','UL','DR','DL',
    # colors
    'WHITE','BLACK','RED','BLUE','GREEN','YELLOW','ORANGE','PURPLE','PINK',
    'GRAY','GREY','DARK_BLUE','DARK_BROWN','DARK_GRAY','DARK_GREY',
    'LIGHT_GRAY','LIGHT_GREY','LIGHT_BROWN','LIGHT_PINK',
    'BLUE_A','BLUE_B','BLUE_C','BLUE_D','BLUE_E',
    'GREEN_A','GREEN_B','GREEN_C','GREEN_D','GREEN_E',
    'RED_A','RED_B','RED_C','RED_D','RED_E',
    'GRAY_A','GRAY_B','GRAY_C','GRAY_D','GRAY_E',
    'TEAL','TEAL_A','TEAL_B','TEAL_C','TEAL_D','TEAL_E',
    'GOLD','GOLD_A','GOLD_B','GOLD_C','GOLD_D','GOLD_E',
    'MAROON','MAROON_A','MAROON_B','MAROON_C','MAROON_D','MAROON_E',
    'PURPLE_A','PURPLE_B','PURPLE_C',
    # math
    'PI','TAU','DEGREES','INF',
    'np',
    # Manim mobjects
    'Text','MathTex','Tex','MarkupText','Paragraph','BulletedList',
    'Circle','Rectangle','Square','Ellipse','Triangle','Polygon','RoundedRectangle',
    'Line','DashedLine','Arrow','DoubleArrow','CurvedArrow','TangentLine',
    'Arc','AnnularSector','Sector','Annulus','ArcBetweenPoints','CubicBezier',
    'ParametricFunction','FunctionGraph',
    'Dot','LabeledDot','SmallDot',
    'VGroup','Group','VDict','always_redraw',
    'NumberLine','Axes','ThreeDAxes','PolarPlane','ComplexPlane',
    'Brace','BraceLabel','BraceBetweenPoints',
    'SurroundingRectangle','BackgroundRectangle','Cross','Checkmark',
    'SVGMobject','ImageMobject',
    'ValueTracker','DecimalNumber','Integer','Variable',
    'MathTable','Table','MobjectTable',
    # animations
    'FadeIn','FadeOut','FadeTransform','FadeTransformPieces',
    'Write','Create','Uncreate','DrawBorderThenFill','ShowIncreasingSubsets',
    'GrowArrow','GrowFromCenter','GrowFromEdge','GrowFromPoint','SpinInFromNothing',
    'Transform','ReplacementTransform','TransformFromCopy','TransformMatchingTex',
    'AnimationGroup','LaggedStart','LaggedStartMap','Succession',
    'Indicate','Circumscribe','Flash','ShowPassingFlash',
    'MoveAlongPath','Rotate','Homotopy',
    'ApplyMethod','ApplyFunction','UpdateFromFunc','UpdateFromAlphaFunc',
    # rate functions
    'smooth','linear','there_and_back','rush_into','rush_from',
    'running_start','double_smooth',
    # builtins
    'True','False','None','self',
    'range','len','print','str','int','float','bool',
    'list','dict','tuple','set','max','min','abs','sum','round',
    'enumerate','zip','map','filter','sorted','reversed',
    'isinstance','hasattr','getattr','setattr','type','any','all',
    # common scene helpers
    'get_svg','show_subtitle','tracker','sub',
    'np','textwrap','os','math','tempfile',
    # short loop vars
    'i','j','k','x','y','z','n','t','r','_',
})


def find_undefined_in_construct(code: str) -> list:
    """
    AST-scan construct() for Name(Load) nodes whose id is never assigned
    inside construct() and is not a known Manim global / builtin.
    Returns sorted list of likely-undefined names.
    """
    try:
        tree = _ast_module.parse(code)
    except SyntaxError:
        return []

    # Collect module-level names (imports, top-level functions/classes/assignments)
    module_names: set = set(_MANIM_GLOBALS)
    for node in tree.body:
        if isinstance(node, _ast_module.FunctionDef):
            module_names.add(node.name)
        elif isinstance(node, _ast_module.ClassDef):
            module_names.add(node.name)
            for item in node.body:
                if isinstance(item, _ast_module.FunctionDef):
                    module_names.add(item.name)
        elif isinstance(node, _ast_module.Assign):
            for t in node.targets:
                if isinstance(t, _ast_module.Name):
                    module_names.add(t.id)
        elif isinstance(node, _ast_module.Import):
            for alias in node.names:
                module_names.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, _ast_module.ImportFrom):
            for alias in node.names:
                if alias.name != '*':
                    module_names.add(alias.asname or alias.name)

    # Find construct()
    construct_node = None
    for node in _ast_module.walk(tree):
        if isinstance(node, _ast_module.FunctionDef) and node.name == 'construct':
            construct_node = node
            break
    if not construct_node:
        return []

    # Collect every name ASSIGNED in construct() — but DO NOT recurse into
    # `with` block bodies.  Variables assigned inside `with self.voiceover():`
    # are NOT visible before that block runs; treating them as "assigned"
    # caused the checker to miss NameErrors like `background not defined`
    # when the model put setup objects inside a voiceover beat instead of
    # the mandatory SETUP BLOCK above the first voiceover.
    assigned: set = set(module_names)

    def _collect_assigned(stmts: list) -> None:
        for stmt in stmts:
            if isinstance(stmt, _ast_module.Assign):
                for t in stmt.targets:
                    if isinstance(t, _ast_module.Name):
                        assigned.add(t.id)
                    elif isinstance(t, _ast_module.Tuple):
                        for elt in t.elts:
                            if isinstance(elt, _ast_module.Name):
                                assigned.add(elt.id)
            elif isinstance(stmt, _ast_module.AugAssign):
                if isinstance(stmt.target, _ast_module.Name):
                    assigned.add(stmt.target.id)
            elif isinstance(stmt, _ast_module.AnnAssign):
                if isinstance(stmt.target, _ast_module.Name):
                    assigned.add(stmt.target.id)
            elif isinstance(stmt, _ast_module.For):
                # Collect loop variable, recurse into body
                tgt = stmt.target
                if isinstance(tgt, _ast_module.Name):
                    assigned.add(tgt.id)
                elif isinstance(tgt, _ast_module.Tuple):
                    for elt in tgt.elts:
                        if isinstance(elt, _ast_module.Name):
                            assigned.add(elt.id)
                _collect_assigned(stmt.body)
            elif isinstance(stmt, _ast_module.If):
                _collect_assigned(stmt.body)
                _collect_assigned(stmt.orelse)
            elif isinstance(stmt, _ast_module.With):
                # Only collect the `as <var>` context variable (e.g. `tracker`).
                # *** DO NOT recurse into stmt.body ***
                # Assignments inside a `with` block (voiceover beats) are not
                # valid definitions for code that runs before the `with` block.
                for item in stmt.items:
                    if item.optional_vars and isinstance(item.optional_vars, _ast_module.Name):
                        assigned.add(item.optional_vars.id)
            elif isinstance(stmt, _ast_module.Try):
                _collect_assigned(stmt.body)
                _collect_assigned(stmt.orelse)
                _collect_assigned(stmt.finalbody if stmt.finalbody else [])

    _collect_assigned(construct_node.body)

    # Find all Load-context names that are not in assigned set
    undefined = []
    seen: set = set()
    for node in _ast_module.walk(construct_node):
        if isinstance(node, _ast_module.Name) and isinstance(node.ctx, _ast_module.Load):
            name = node.id
            if name not in assigned and name not in seen and len(name) >= 2:
                undefined.append(name)
                seen.add(name)

    return sorted(undefined)


def fix_missing_definitions_pass(code: str, undefined: list) -> str:
    """
    Targeted Claude pass: given a list of undefined names, ask Claude to
    insert only their definitions in the SETUP BLOCK. No other changes.
    """
    if not undefined:
        return code
    names_str = ', '.join(f'`{n}`' for n in undefined[:20])   # cap at 20
    logger.info(f"🔧 Running targeted fix pass for: {names_str}")
    fix_prompt = f"""The Manim code below will crash with NameError because these variables are used
in animations but never defined: {names_str}

YOUR ONLY TASK:
1. Find `def construct(self):` and the `self.set_speech_service(...)` line inside it.
2. Immediately after set_speech_service, insert a SETUP BLOCK that defines ALL of: {names_str}
3. Infer the correct Manim object type for each name from how it is used in the animation code.
4. Do NOT change any animation code — only add definitions.
5. Return the COMPLETE corrected Python file.

DEFINITION RULES:
- background / bg       → Rectangle(width=15, height=9, fill_color="#0d0d1a", fill_opacity=1, stroke_width=0)
- grid_lines            → VGroup of Line objects covering the scene
- Names ending _svg     → replace with appropriate Manim primitives (no SVGMobject)
- Names ending _card    → Rectangle with fill_color and stroke_color
- Names ending _formula → MathTex(r"...", font_size=30, color=YELLOW)
- Names ending _text    → Text("...", font_size=26, color=WHITE)
- Names ending _arrow   → Arrow(LEFT*2, RIGHT*2, color=YELLOW, buff=0)
- Names ending _label   → Text("...", font_size=20, color=WHITE)
- Names ending _lines / _dots / _group → VGroup of appropriate sub-objects
- Any composite (cup, car_shape, etc.) → VGroup assembled from Polygon/Rectangle/Circle parts

CODE:
```python
{code}
```"""

    try:
        response = claude_with_retry(
            _claude_sync.messages.create,
            model=_CLAUDE_MODEL,
            max_tokens=16000,
            messages=[{"role": "user", "content": fix_prompt}],
        )
        fixed = response.content[0].text.strip()
        for fence in ("```python", "```"):
            if fixed.startswith(fence):
                fixed = fixed[len(fence):].strip()
        if fixed.endswith("```"):
            fixed = fixed[:-3].strip()
        try:
            _ast_module.parse(fixed)
        except SyntaxError as e:
            logger.warning(f"⚠️  Fix pass produced invalid syntax — keeping original: {e}")
            return code
        if len(fixed) > 200:
            logger.info(f"✅ Fix pass applied ({len(fixed)} chars)")
            return fixed
    except Exception as e:
        logger.warning(f"⚠️  Fix pass failed (non-fatal): {e}")
    return code


def claude_with_retry(fn, *args, max_retries=4, **kwargs):
    """Retry on overloaded_error / HTTP 529 with exponential back-off: 5s, 15s, 45s, 135s."""
    delays = [5, 15, 45, 135]
    for attempt, delay in enumerate(delays[:max_retries], 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            err_str = str(exc)
            is_overloaded = (
                "overloaded_error" in err_str
                or "overloaded" in err_str.lower()
                or "529" in err_str
            )
            if is_overloaded and attempt <= max_retries:
                logger.warning(
                    f"Claude overloaded (attempt {attempt}/{max_retries}) — retrying in {delay}s"
                )
                time.sleep(delay)
            else:
                raise
    return fn(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────────────
# TTS HELPERS
# ─────────────────────────────────────────────────────────────────────────────────────

def get_tts_prompt_blocks() -> tuple[str, str]:
    """Return (tts_import_line, tts_service_block) based on TTS_SERVICE env var."""
    service = os.environ.get("TTS_SERVICE", "azure").lower().strip()
    if service == "gtts":
        tts_import = "from manim_voiceover.services.gtts import GTTSService"
        tts_block = """self.set_speech_service(GTTSService(lang="LANG_CODE"))
- Choose lang based on the language of the narration:
  - Finnish  → fi
  - Swedish  → sv
  - English  → en
  - Hindi    → hi
  - Tamil    → ta
- If unsure, default to lang="en"
- NOTE: GTTSService requires no API keys"""
    else:
        tts_import = "from manim_voiceover.services.azure import AzureService"
        tts_block = """self.set_speech_service(AzureService(voice="VOICE_NAME", global_speed=0.90))
- Choose voice based on the language of the narration:
  - Finnish  → fi-FI-NooraNeural
  - Swedish  → sv-SE-SofieNeural
  - English  → en-US-JennyNeural
  - Hindi    → hi-IN-SwaraNeural
  - Tamil    → ta-IN-PallaviNeural
- If unsure, default to voice="en-US-JennyNeural"
- NOTE: AzureService requires AZURE_SPEECH_KEY and AZURE_SPEECH_REGION env vars"""
    return tts_import, tts_block


def apply_tts_placeholders(template: str) -> str:
    """Replace {{TTS_IMPORT}} and {{TTS_SERVICE_BLOCK}} in a prompt template."""
    tts_import, tts_block = get_tts_prompt_blocks()
    return template.replace("{{TTS_IMPORT}}", tts_import).replace("{{TTS_SERVICE_BLOCK}}", tts_block)


# ─────────────────────────────────────────────────────────────────────────────────────
# CHATGPT SYSTEM PROMPT — copied verbatim from AnimLearn
# ─────────────────────────────────────────────────────────────────────────────────────

CHATGPT_SYSTEM_PROMPT = """
You are an expert problem solver and tutor (chemistry, physics, mathematics, economics).
Your task is to produce a CORRECT, educational, and well-structured solution
that will be used for:
1. Educational video generation (AnimLearn)
2. Conversational AI tutoring with step-by-step guidance
3. Student practice and learning

INPUT TYPE:
- You may receive a text problem, an image, or both.
- If an image is provided, it may contain diagrams, graphs, experiments, or chemical/physics setups.
- If both text and image are provided, use the image as additional context and do not repeat information unnecessarily.
- If only an image is provided, interpret the image content and extract the question/problem, variables, and relevant data as accurately as possible.

ABSOLUTE RULES:
- Prioritize correctness over verbosity
- Adapt explanation depth to TARGET_DURATION
- Use ONLY the requested LANGUAGE
- Do NOT generate Manim code or visuals
- Make each step independently understandable for conversational tutoring
- If you cannot extract information from the image, clearly state assumptions made

CHEMISTRY SPECIFIC RULES (apply only when subject = chemistry):
- Do NOT use Henderson-Hasselbalch equation unless BOTH weak acid AND conjugate base are explicitly given
- For pure weak acids, always solve using Ka equilibrium
- Never assume concentrations not given
- Always show chemical equations with proper phases (s, l, g, aq)
- Use smallest whole number coefficients in balanced equations

CHEMISTRY NAMING RULE (apply only when subject = chemistry, MANDATORY):
- NEVER read chemical formulas letter-by-letter in voiceover
- ALWAYS convert formulas to proper chemical names in spoken text
- Visual formulas (e.g., ZnCl₂, H₂SO₄) are allowed on screen
- Spoken language must use:
  - English: zinc chloride, sulfuric acid, carbon dioxide
  - Finnish: sinkkikloridi, rikkihappo, hiilidioksidi
  - Swedish: zinkklorid, svavelsyra, koldioxid

PHYSICS SPECIFIC RULES (apply only when subject = physics):
- Always state which law or principle justifies each step (Newton's 2nd, conservation of energy, etc.)
- Include free-body diagrams or component decomposition described textually when forces are involved
- Use SI units consistently; convert non-SI units before calculating
- Clearly distinguish scalar vs. vector quantities; specify direction for vectors

MATHEMATICS SPECIFIC RULES (apply only when subject = mathematics):
- Show every algebraic manipulation step — do not skip steps
- State the domain or constraints before solving
- For calculus: write the limit definition or rule name used (chain rule, product rule, etc.)
- Box or highlight the final simplified form

STRUCTURE (MANDATORY):
Your solution MUST have these EXACT sections:

### GIVEN
- List all provided information clearly
- Include units for all values
- State the question/problem to solve
- Reference chemical equations or image data if applicable

### FORMULAS
- List ALL relevant formulas, laws, and principles
- Include formula names (e.g., "Ideal Gas Law: PV = nRT")
- Add brief context for each formula
- Include constants with values and units
- Each formula on separate line starting with "-" or "•"

### CALCULATION
- Break solution into numbered steps (Step 1, Step 2, etc.)
- Each step should be independently understandable
- Show intermediate calculations clearly
- Include units in every calculation
- Explain the reasoning for each step
- Use clear variable definitions
- Each major step should start on a new line

### RESULT
- State final answer clearly and prominently
- Include correct units
- Use proper significant figures
- Restate the question being answered
- For multi-part questions, list all answers

### INTERPRETATION
- Explain what the result means physically/chemically
- Connect to real-world context if relevant
- Mention common mistakes students make
- Add conceptual insights
- Suggest related concepts to study

CALCULATION FORMATTING FOR TUTORING:
Make calculations easy to follow conversationally:
✓ GOOD: "Step 1: Calculate moles of NaCl
         n = m/M = 5.85g / 58.5 g/mol = 0.1 mol"
✗ BAD: "n = 5.85/58.5 = 0.1 mol" (no context)

CONCEPT ABSTRACTION (MANDATORY):
- Extract an abstract, examiner-level description of the knowledge being tested.
- This will be used to generate NEW practice problems without reusing or paraphrasing the original question.
- Rules:
  - DO NOT copy or paraphrase the original question
  - DO NOT mention specific numbers, materials, experiments, or examples unless essential
  - Write in neutral, syllabus-level language
  - Focus on what must remain invariant across all equivalent problems

══════════════════════════════════════════════════════════════
VIDEO NARRATION — STORYTELLING RULES (MANDATORY for video_script field)
══════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────
TEACHER PERSONA
────────────────────────────────────────────────────────────
You are a world-class science communicator — think Veritasium meets
3Blue1Brown. You find the hidden drama in every equation. You know that
students don't remember facts; they remember the MOMENT something clicked.
Your narration is designed to manufacture that moment.

────────────────────────────────────────────────────────────
THE SINGLE MOST IMPORTANT RULE: OPEN A QUESTION LOOP
────────────────────────────────────────────────────────────
The human brain cannot rest with an open question. Exploit this.

STEP 1 — OPEN THE LOOP at the very start (the hook):
  Pose a specific, concrete question the student genuinely doesn't know the answer to yet.

STEP 2 — HOLD THE TENSION throughout the build:
  Refer back to the open question during calculations.

STEP 3 — CLOSE THE LOOP at the reveal:
  Answer the exact question you opened. Make it feel earned.

────────────────────────────────────────────────────────────
HOOK PATTERNS — CHOOSE THE BEST FIT (MANDATORY: use one)
────────────────────────────────────────────────────────────

PATTERN A — THE COUNTERINTUITIVE CHALLENGE
PATTERN B — THE REAL-WORLD MYSTERY
PATTERN C — THE SURPRISING NUMBER
PATTERN D — THE STAKES/CONSEQUENCE
PATTERN E — THE BEAUTIFUL PATTERN (for mathematics)

────────────────────────────────────────────────────────────
NARRATIVE ARC (MANDATORY)
────────────────────────────────────────────────────────────

  1. HOOK + QUESTION LOOP OPEN (5–10s)
  2. SCENE-SETTING (5–8s)
  3. BUILD — each step is a DISCOVERY (8–15s per step)
  4. THE PIVOT (3–5s, optional but powerful)
  5. REVEAL — close the question loop (5–8s)
  6. SO WHAT + CALLBACK (8–12s)

────────────────────────────────────────────────────────────
[BEAT] MARKERS — MANDATORY
────────────────────────────────────────────────────────────
Embed [BEAT: description | emotion] tags to mark every visual transition.

FORMAT: [BEAT: what appears or moves on screen | emotion: word]

EMOTION TAGS: curious, building, surprise, pivot, reveal, satisfy, dramatic

RULES:
- One [BEAT] per narration block minimum
- Place [BEAT] BEFORE the narration sentence it accompanies
- Every new object → [BEAT: object appears | emotion: curious]
- Every force arrow → [BEAT: force arrow grows | emotion: building]
- Every key formula → [BEAT: formula appears | emotion: building]
- Every object motion → [BEAT: object moves | emotion: dramatic]
- The pivot moment → [BEAT: key insight highlighted | emotion: pivot]
- The final answer → [BEAT: result shown | emotion: reveal]
- The callback/close → [BEAT: callback to hook | emotion: satisfy]

SUBJECT DETECTION (MANDATORY):
Scan the input and pick the single best-fitting subject:
- "chemistry": chemical formulas, reactions, pH, Ka, Kb, stoichiometry, acid/base
- "physics": force, velocity, acceleration, energy, circuits, waves, optics, kinematics
- "mathematics": pure algebra, derivatives, integrals, geometry — NO physical units
- "economics": supply/demand, GDP, elasticity, market equilibrium
- "biology": cells, DNA, proteins, genetics, ecosystems
- "general": genuinely cross-disciplinary

OUTPUT FORMAT (MANDATORY):
Return output in EXACTLY this JSON format:

{
  "structured_solution": "...",
  "transcript_markdown": "...",
  "video_script": "...",
  "subject": "<exactly one of: chemistry | physics | mathematics | economics | biology | general>",
  "tags": ["5–10 relevant tags"],
  "topic_keywords": ["2-5 specific topic keywords"],
  "concept_abstraction": {
      "core_concept": "...",
      "cognitive_skill": "...",
      "allowed_variations": ["...", "..."],
      "disallowed_variations": ["...", "..."]
  }
}

FIELD REQUIREMENTS:

1. "structured_solution": plain text with ### section headers (GIVEN, FORMULAS, CALCULATION, RESULT, INTERPRETATION)
2. "transcript_markdown": Markdown LEARNING REFERENCE with LaTeX math, **bold**, numbered steps
3. "video_script": CINEMATIC NARRATION SCRIPT — flowing, [BEAT] markers, no section headers

Output ONLY valid JSON. No preamble, no markdown code blocks, just the JSON object.
"""


# ─────────────────────────────────────────────────────────────────────────────────────
# ULTIMATE MANIM SYSTEM PROMPT — copied verbatim from AnimLearn
# ─────────────────────────────────────────────────────────────────────────────────────

_ULTIMATE_SYSTEM_PROMPT_TEMPLATE = r"""You are an expert Manim educational animation code generator with MANDATORY voiceover support.
══════════════════════════════════════════════════════════════════
⚠️  NON-NEGOTIABLE REQUIREMENT — READ BEFORE ANYTHING ELSE
══════════════════════════════════════════════════════════════════

EVERY construct() MUST follow this exact two-phase structure:

    def construct(self):
        self.set_speech_service(...)

        # ═══ PHASE 1: SETUP — define ALL objects here, before any voiceover ═══
        background  = Rectangle(width=15, height=9, fill_color="#0d0d1a", ...)
        grid_lines  = VGroup(Line(...), Line(...), ...)
        title       = Text("...", font_size=36, color=WHITE)
        formula     = MathTex(r"F = ma", font_size=32, color=YELLOW)
        car_body    = Rectangle(...)
        car_wheel   = Circle(...)
        car_shape   = VGroup(car_body, car_wheel)
        blur_lines  = VGroup(Line(...), ...)
        # ... EVERY name you will pass to self.play(), self.add(),
        # FadeIn(), FadeOut(), GrowArrow(), Indicate(), VGroup(), etc.
        # MUST be assigned here — no exceptions.
        # ═══ END PHASE 1 ══════════════════════════════════════════════════

        self.add(background, grid_lines)   # safe — both defined above

        # ═══ PHASE 2: ANIMATIONS — ordered voiceover beats ════════════════
        with self.voiceover(text="...") as tracker:
            sub = self.show_subtitle("...")
            self.play(FadeIn(title))        # safe — title defined above
            self.wait(max(0.1, tracker.duration - 0.5))
        self.play(FadeOut(sub))

WHAT KILLS THE RENDER (NameError — do NOT do these):
❌  self.add(background, grid_lines)           # background never assigned
❌  with self.voiceover(...):
        car = VGroup(body, wheel)              # defined inside beat → crash
❌  self.play(FadeIn(blur_lines))              # blur_lines never assigned

══════════════════════════════════════════════════════════════════
ROLE OVERRIDE — READ CAREFULLY
══════════════════════════════════════════════════════════════════

You are NOT a problem solver.

You are a VISUALIZATION ENGINE.

The mathematical and scientific solution is ALREADY VERIFIED
and PROVIDED BY ANOTHER SYSTEM.

ABSOLUTE PROHIBITIONS:
- DO NOT recompute
- DO NOT simplify
- DO NOT re-derive
- DO NOT change numbers
- DO NOT introduce new formulas
- DO NOT infer missing steps
- DO NOT "fix" anything

If a value appears strange, YOU MUST STILL USE IT AS-IS.

Your ONLY job:
- Turn the provided solution into Manim visuals
- Synchronize voiceover narration with the solution text
- Preserve numerical and symbolic fidelity EXACTLY
- Adapt layout to TARGET_ASPECT_RATIO
- USE THE FULL SCREEN SPACE AVAILABLE

══════════════════════════════════════════════════════════════════
ABSOLUTE RULES — MUST FOLLOW EXACTLY
══════════════════════════════════════════════════════════════════

1. Scene & Voiceover
- Generate EXACTLY ONE class inheriting from VoiceoverScene
- NEVER use Scene
- ALWAYS wrap ALL animations inside:
  with self.voiceover(text="..."):

2. REQUIRED IMPORTS (must be exactly these):
from manim import *
from manim_voiceover import VoiceoverScene
{{TTS_IMPORT}}

3. Voice Service (inside construct):
{{TTS_SERVICE_BLOCK}}

4. SUBTITLE SYSTEM (MANDATORY)

Add show_subtitle as a CLASS METHOD — defined at the same indentation level as construct(), NOT inside construct():

class YourScene(VoiceoverScene):
    def show_subtitle(self, text, duration=None):
        import textwrap
        wrapped = "\n".join(textwrap.wrap(text, width=60))
        subtitle = Text(wrapped, font_size=18, color=WHITE, line_spacing=1.2).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(subtitle))
        if duration:
            self.wait(duration)
        return subtitle

    def construct(self):
        ...

USAGE PATTERN:
with self.voiceover(text="...") as tracker:
    sub = self.show_subtitle("Same text as voiceover")
    # ... animations ...
    self.wait(max(0.1, tracker.duration - 0.5))
self.play(FadeOut(sub))

SUBTITLE RULES:
- show_subtitle MUST be a class method, NEVER a nested function inside construct()
- Every voiceover block MUST have a matching subtitle
- Call as self.show_subtitle(...), NEVER as show_subtitle(self, ...)
- Remove subtitle (FadeOut) before starting the next voiceover block
- Never stack subtitles — only one visible at a time

══════════════════════════════════════════════════════════════════
LAYOUT RULES (MANDATORY)
══════════════════════════════════════════════════════════════════

CANVAS ZONES:
- TOP    (y > 2.5):   Titles and section headers only
- MIDDLE (-2 < y < 2): Main content — diagrams, equations, text
- BOTTOM (y < -2.5):  Subtitles ONLY — never place content here

TEXT SIZE LIMITS:
- Titles:    font_size <= 36
- Body text: font_size <= 28
- Subtitles: font_size = 18 (fixed)
- Labels:    font_size <= 20

ELEMENT LIMITS:
- Maximum 5 elements visible on screen at once
- Use FadeOut before adding new content if screen is full

POSITIONING RULES:
- Always use explicit positioning (never leave at ORIGIN by default)
- Use .next_to(obj, direction, buff=0.3) for relative placement
- Use .to_edge(direction, buff=0.5) for screen edges
- Never overlap elements

══════════════════════════════════════════════════════════════════
MATHEMATICS VIDEO RULES
══════════════════════════════════════════════════════════════════

- Use MathTex for ALL mathematical expressions (never Text for formulas)
- Stack equations vertically using VGroup + arrange(DOWN, buff=0.4)
- Show one equation/step at a time — FadeOut previous before showing next
- Highlight key terms with Indicate or Circumscribe
- Use TransformMatchingTex when morphing one equation into another

══════════════════════════════════════════════════════════════════
PHYSICS VIDEO RULES
══════════════════════════════════════════════════════════════════

- Draw diagram/apparatus FIRST, then animate labels appearing
- Keep formula in TOP zone while running animation in MIDDLE zone
- Use Arrow for force/vector indicators, label near arrowhead
- Animate motion with UpdateFromAlphaFunc or MoveAlongPath

PHYSICS SCENE QUALITY (MANDATORY):

SCENE LAYOUT for mechanics problems:
  - LEFT half of screen (x < 0): the physical scene (object + terrain + force arrows)
  - RIGHT half (x > 1.5): equations and labels — NEVER overlap with the diagram
  - Terrain: draw the hill/ground with Polygon(), fill_opacity=0.3, stroke_width=3

FORCE ARROWS — use GrowArrow() NOT Create() for cinematic effect:
  grav_arrow = Arrow(bicycle.get_center(), bicycle.get_center()+DOWN*1.8, color=RED, buff=0, stroke_width=5)
  self.play(GrowArrow(grav_arrow), run_time=0.9)

VEHICLE MOTION along a slope — use MoveAlongPath:
  slope_path = ArcBetweenPoints(start_pos, end_pos, angle=0)
  self.play(MoveAlongPath(bicycle, slope_path), run_time=2.5, rate_func=linear)

DYNAMIC FORMULA UPDATES — use DecimalNumber + ValueTracker for live displays.

INDICATE key formula terms when narrating them:
  self.play(Indicate(formula[0][3], color=RED, scale_factor=1.5))

══════════════════════════════════════════════════════════════════
CHEMISTRY VIDEO RULES
══════════════════════════════════════════════════════════════════

- Atom circles: Circle(radius=0.4) with element symbol Text inside
- Bond lines: Line(stroke_width=3) connecting atom centers
- Center molecule at ORIGIN, then shift to MIDDLE zone
- For reactions: show reactants LEFT → Arrow (center) → products RIGHT
- Color-code by element: O=RED, H=WHITE, C=GRAY, N=BLUE

CHEMISTRY NAMING RULE (MANDATORY):
- NEVER read chemical formulas letter-by-letter in voiceover
- ALWAYS convert formulas to proper chemical names in spoken text

══════════════════════════════════════════════════════════════════
GENERAL ANIMATION RULES
══════════════════════════════════════════════════════════════════

- Use FadeIn/FadeOut for all element transitions
- Use GrowArrow() for any Arrow that represents a force, velocity, or vector — NOT Create()
- Use DrawBorderThenFill() for filled shapes
- Use AnimationGroup([...], lag_ratio=0.15) to stagger related elements
- Minimum wait between animations: 0.5 seconds
- NEVER use VGroup(*self.mobjects) — use Group(*self.mobjects) instead
- When an SVG object moves, move force arrows WITH it in the same play() call

CRASH PREVENTION:

a) ZERO-LENGTH DashedLine / Line:
   RULE: Before EVERY DashedLine or Line, guard with a length check:
       _s, _e = np.array([x1,y1,0]), np.array([x2,y2,0])
       if np.linalg.norm(_e - _s) > 0.01:
           my_line = DashedLine(_s, _e, ...)

b) NEGATIVE self.wait() duration:
   RULE: Use self.wait(max(0.1, tracker.duration - X)) everywhere.

COLOR CODING (consistent):
- Titles: WHITE  |  Equations: YELLOW  |  Highlights: RED
- Diagrams: BLUE and GREEN  |  Labels: WHITE or LIGHT_GRAY  |  Arrows: YELLOW or ORANGE

5. SETUP BLOCK — MANDATORY, NO EXCEPTIONS

construct() MUST follow this two-phase structure:

    def construct(self):
        self.set_speech_service(...)

        # ══ PHASE 1: SETUP — define EVERY object before ANY animation ══
        title         = Text("...", ...)
        subtitle_var  = Text("...", ...)
        formula       = MathTex(r"...", ...)
        arrow         = Arrow(LEFT, RIGHT, ...)
        diagram_group = VGroup(rect, label, arrow)
        # ─ ALL objects used in ANY voiceover block below must exist here ─

        # ══ PHASE 2: ANIMATIONS — ordered voiceover beats ══
        with self.voiceover(text="...") as tracker:
            sub = self.show_subtitle("...")
            self.play(FadeIn(title))
            self.wait(max(0.1, tracker.duration - 0.5))
        self.play(FadeOut(sub))
        ...

CRITICAL RULES FOR THE SETUP BLOCK:
- Every variable referenced inside ANY self.play(), self.add(), VGroup(),
  AnimationGroup(), FadeIn(), FadeOut(), GrowArrow(), Indicate(), etc.
  MUST be assigned in the SETUP BLOCK above the first voiceover block.
- NEVER define an object for the first time inside a voiceover block.
  If you write `foo = Circle()` inside beat 3, beat 1 cannot use it.
- Assemble VGroups in the SETUP BLOCK, not inside animation beats.
- Objects that depend on other objects (e.g. steam that needs cup_top_pos)
  must both be defined in the SETUP BLOCK in dependency order.

BANNED — these patterns cause NameError at render time:
❌  with self.voiceover(...):
        my_arrow = Arrow(...)   # ← defining here means later beats crash
        self.play(GrowArrow(my_arrow))

❌  self.play(FadeIn(cup))          # ← cup was never assigned above

CORRECT — define everything first, then animate:
✅  cup = VGroup(body, handle, saucer)   # in SETUP BLOCK
    ...
    with self.voiceover(...):
        self.play(FadeIn(cup))           # ← safe: cup already exists

6. Colors (STRICT)
Use ONLY: RED, BLUE, GREEN, YELLOW, ORANGE, PURPLE, PINK, WHITE, BLACK, GRAY, GREY

══════════════════════════════════════════════════════════════════
MOLECULAR VISUALIZATION (CHEMISTRY)
══════════════════════════════════════════════════════════════════

For chemistry problems involving molecules, use:
from helpers import create_molecule_from_smiles

COMMON SMILES: Water="O", CO2="O=C=O", Methane="C", Ammonia="N", Ethanol="CCO", Benzene="c1ccccc1"

METHOD 1: MANUAL CONSTRUCTION — simple inorganic (≤5 atoms, H₂O, CO₂, NH₃, HCl)
METHOD 2: RDKIT SMILES HELPER — organic & complex (any C-chain, ≥6 atoms)

══════════════════════════════════════════════════════════════════
HELPER FUNCTIONS AVAILABLE
══════════════════════════════════════════════════════════════════

Import at the top: from helpers import *

- create_water_pipe_ohms_law() — Ohm's Law water analogy (MANDATORY for V=IR)
- create_energy_bars(pe, ke)  — PE/KE bar charts for energy conservation
- create_force_diagram(obj, forces_dict) — free body diagrams
- create_molecule_from_smiles(smiles, position, scale) — molecular structures

══════════════════════════════════════════════════════════════════
CRITICAL: SEQUENTIAL DISPLAY ONLY (MANDATORY)
══════════════════════════════════════════════════════════════════

ALWAYS show elements sequentially — never molecule + text simultaneously.
FadeOut old content before showing new content at the same position.

══════════════════════════════════════════════════════════════════
ASPECT RATIO LAYOUT STRATEGY (MANDATORY)
══════════════════════════════════════════════════════════════════

TARGET_ASPECT_RATIO will be provided: 16:9, 9:16, 1:1, or 4:5

16:9 (LANDSCAPE): Side-by-side — Diagram LEFT * 3, Formulas RIGHT * 2.5
9:16 (PORTRAIT):  Top-bottom — Diagram UP * 5.5 to UP * 2.5, Formulas UP * 1.5 to DOWN * 5
1:1 (SQUARE):     Top-bottom — Diagram UP * 2.5, Formulas DOWN * 1.5
4:5 (PORTRAIT):   Top-bottom compact

FONT SIZES:
- 16:9: titles 32-36, body 28-32, labels 20-24
- 9:16: titles 32-36, body 28-32 (NOT 24!), generous 1.2-1.5 unit spacing
- 1:1: titles 30-34, body 26-30

FOR 9:16 — USE FULL VERTICAL SPACE:
- Total range: UP * 5.5 to DOWN * 5 (10.5 units)
- NEVER put molecule below UP * 1
- NEVER put text above DOWN * 1.5

══════════════════════════════════════════════════════════════════
CRITICAL POSITION & COORDINATE RULES (NO EXCEPTIONS)
══════════════════════════════════════════════════════════════════

CORRECT: Line(LEFT, RIGHT)  |  Circle().shift(LEFT*2 + UP*1)  |  Text("Hi").move_to(RIGHT*3 + DOWN*2)
NEVER:   Line([LEFT*2, UP, 0], [...])  |  obj.move_to([LEFT*2+i, UP, 0])

Directional constants: ORIGIN, UP, DOWN, LEFT, RIGHT, IN, OUT
Object positions: get_center(), get_top(), get_bottom(), get_left(), get_right()

══════════════════════════════════════════════════════════════════
ANIMATION DIRECTION — CINEMATIC STYLE GUIDE (MANDATORY)
══════════════════════════════════════════════════════════════════

CINEMATIC BEAT STRUCTURE:
BEAT 1 — ESTABLISH: Draw the world (terrain, object). No arrows yet.
BEAT 2 — INTRODUCE FORCES: Reveal force arrows one by one with GrowArrow().
BEAT 3 — ANIMATE MOTION: Move object along path. ALL arrows shift() in same play().
BEAT 4 — SHOW CHANGE: Update formula values with DecimalNumber + ValueTracker.
BEAT 5 — CONCLUDE: Circumscribe() final answer. FadeOut everything except result.

BANNED PATTERNS:
❌ STATIC OBJECT + TEXT DUMP — every text must appear while something moves
❌ STATIC FORCE ARROWS — arrows MUST move with the object
❌ SHAPELESS OBJECTS — never use Dot(radius=0.01) as a placeholder
❌ CROWDED SCREEN — never >5 visible elements at once
❌ VGroup(*self.mobjects) — always use Group(*self.mobjects)

SLOPE GEOMETRY (MANDATORY FOR PHYSICS):
  import numpy as np
  theta = np.radians(ANGLE_DEGREES)
  slope_dir  = np.array([np.cos(theta), -np.sin(theta), 0])   # along slope downhill
  normal_dir = np.array([np.sin(theta),  np.cos(theta), 0])   # perpendicular to slope

  gravity_dir  = np.array([0, -1, 0])    # always straight DOWN
  friction_dir = -slope_dir              # up the slope (opposing slide)

══════════════════════════════════════════════════════════════════
DURATION GUIDELINES
══════════════════════════════════════════════════════════════════

- Each voiceover block ≈ 5–8 seconds
- 30s → 2–3 blocks  |  1 min → 4–5 blocks  |  2 min → 7–9 blocks  |  3 min → 10–12 blocks

CLASS NAMING RULE: Scene class name MUST be in English; screen titles in TARGET_LANGUAGE.

══════════════════════════════════════════════════════════════════
SELF-VALIDATION STEP (MANDATORY)
══════════════════════════════════════════════════════════════════

Before outputting, verify:
✔ Uses VoiceoverScene, exactly one class
✔ All animations inside voiceover blocks
✔ Layout matches TARGET_ASPECT_RATIO
✔ If 9:16, uses FULL vertical space (UP * 5.5 to DOWN * 5)
✔ No overlapping between zones
✔ No invalid colors
✔ No nested coordinate arrays
✔ Code is valid Manim Python
✔ Main object physically MOVES at least once (not static!)
✔ Force arrows use GrowArrow(), not Create()
✔ Force arrows shift() together with object in same play() call
✔ Normal force direction is perpendicular to surface
✔ No static text dumps — every block has motion/animation
✔ Screen never has >5 elements simultaneously

UNDEFINED VARIABLE CHECK (MANDATORY — run mentally before output):
✔ A two-phase structure exists: SETUP BLOCK first, then animation beats
✔ Every name passed to self.play(), FadeIn(), FadeOut(), GrowArrow(),
  VGroup(), AnimationGroup(), Indicate(), Circumscribe(), etc. is
  ALREADY ASSIGNED in the SETUP BLOCK above the first voiceover block
✔ No object is defined for the first time inside a voiceover block
✔ VGroups are assembled from parts that are all defined above them
✔ If you use cup, steam_lines, crystal_dots, diagram_group, laws_summary,
  final_cup, or ANY composite object — it is built in the SETUP BLOCK
✔ Zero NameErrors would occur if Python executed the code top-to-bottom

══════════════════════════════════════════════════════════════════
OUTPUT FORMAT (STRICT)
══════════════════════════════════════════════════════════════════

Return:
1️⃣ Manim code ONLY
2️⃣ Then on a new line, exactly:

###METADATA###
{
  "subject": "chemistry|physics|mathematics|economics",
  "tags": ["5–10 relevant tags"],
  "estimated_duration": <seconds>
}

FAILURE CONDITION

If the provided solution is incomplete or unclear:
Output ONLY: ERROR: INVALID SOLUTION INPUT
"""

ULTIMATE_SYSTEM_PROMPT = apply_tts_placeholders(_ULTIMATE_SYSTEM_PROMPT_TEMPLATE)


def _build_system_prompt(subject: str, aspect_ratio: str, language: str) -> str:
    """Build dynamic system prompt: ULTIMATE_SYSTEM_PROMPT + runtime config vars."""
    runtime_config = f"""

══════════════════════════════════════════════════════════════════
RUNTIME CONFIGURATION
══════════════════════════════════════════════════════════════════

TARGET_ASPECT_RATIO: {aspect_ratio}
TARGET_LANGUAGE: {language}

Adapt all positioning and font sizes according to TARGET_ASPECT_RATIO rules above.
Use TARGET_LANGUAGE for voiceover text and screen titles.
"""
    return ULTIMATE_SYSTEM_PROMPT + runtime_config


# ─────────────────────────────────────────────────────────────────────────────────────
# LAYOUT FIXERS — copied verbatim from AnimLearn
# ─────────────────────────────────────────────────────────────────────────────────────

def fix_molecular_layout(code: str, aspect_ratio: str = "9:16") -> str:
    if aspect_ratio == "9:16":
        code = fix_9_16_layout(code)
    elif aspect_ratio == "16:9":
        code = fix_16_9_layout(code)
    else:
        code = fix_square_layout(code)
    code = fix_text_overlaps(code)
    return code


def fix_9_16_layout(code: str) -> str:
    has_comparison = bool(re.search(r'(mol[12]_final|nh3_final|ch4_final|\w+_final.*\w+_final)', code, re.IGNORECASE))
    fixes = []
    fixes.append((
        r'title\.move_to\(UP \* [0-5](?:\.[0-9]+)?\)',
        'title.move_to(UP * 6)',
        "Moving title to top"
    ))
    if not has_comparison:
        fixes.extend([
            (r'create_molecule_from_smiles\(([^)]*?)position\s*=\s*(LEFT|RIGHT)\s*\*\s*[0-9]+(?:\.[0-9]+)?\s*\+\s*UP\s*\*\s*[0-9]+(?:\.[0-9]+)?',
             r'create_molecule_from_smiles(\1position=UP * 2.5',
             "Centering single molecules"),
            (r'create_molecule_from_smiles\(([^)]*?)position\s*=\s*(LEFT|RIGHT)\s*\*\s*[0-9]+(?:\.[0-9]+)?(?!\s*\+)',
             r'create_molecule_from_smiles(\1position=UP * 2.5',
             "Centering single molecules (no UP)"),
        ])
    else:
        fixes.append((
            r'(?<!_final)\s*=\s*create_molecule_from_smiles\(([^)]*?)position\s*=\s*(LEFT|RIGHT)\s*\*\s*[0-9]+',
            r' = create_molecule_from_smiles(\1position=UP * 2.5',
            "Centering non-comparison molecules"
        ))
        fixes.append((
            r'(\w+_final)\s*=\s*create_molecule_from_smiles\(([^)]*?)position\s*=\s*UP\s*\*\s*[0-9.]+(?!\s*\+)',
            r'\1 = create_molecule_from_smiles(\2position=LEFT * 2 + UP * 2.5',
            "Fixing comparison molecule position (LEFT)"
        ))
    fixes.append((
        r'create_molecule_from_smiles\(([^)]*?)position\s*=\s*UP\s*\*\s*3(?:\.0)?(?![0-9])',
        r'create_molecule_from_smiles(\1position=UP * 2.5',
        "Adjusting molecule height"
    ))
    if not has_comparison:
        fixes.append((
            r'create_molecule_from_smiles\(([^)]*?)scale\s*=\s*2\.[0-5](?![0-9])',
            r'create_molecule_from_smiles(\1scale=3.0',
            "Increasing single molecule scale"
        ))
    else:
        fixes.append((
            r'(?<!_final)\s*=\s*create_molecule_from_smiles\(([^)]*?)scale\s*=\s*2\.[0-5]',
            r' = create_molecule_from_smiles(\1scale=3.0',
            "Increasing non-comparison molecule scale"
        ))
        fixes.append((
            r'_final\s*=\s*create_molecule_from_smiles\(([^)]*?)scale\s*=\s*3\.0',
            r'_final = create_molecule_from_smiles(\1scale=2.5',
            "Reducing comparison molecule scale"
        ))
    fixes.extend([
        (r'(text[0-9]*|explanation[0-9]*|label[0-9]*|geometry_text[0-9]*|structure_text[0-9]*)\.move_to\(UP \* [0-9]+(?:\.[0-9]+)?\)',
         r'\1.move_to(DOWN * 2)',
         "Moving text to bottom zone"),
        (r'(text[0-9]*|explanation[0-9]*|label[0-9]*)\.move_to\(ORIGIN\)',
         r'\1.move_to(DOWN * 2)',
         "Moving text from center to bottom"),
        (r'(text[0-9]*|explanation[0-9]*|label[0-9]*)\.move_to\(DOWN \* [0-1](?:\.[0-9]+)?\)',
         r'\1.move_to(DOWN * 2)',
         "Adjusting text lower"),
    ])
    fixes.append((
        r'title\.animate\.scale\([0-9.]+\)\.to_edge\(UP\)',
        'title.animate.scale(0.6).move_to(UP * 6.5)',
        "Keeping title at top"
    ))
    fixes.extend([
        (r'font_size\s*=\s*2[0-6](?![0-9])', 'font_size=30', "Increasing font size for mobile"),
        (r'font_size\s*=\s*28(?![0-9])',      'font_size=30', "Increasing font size"),
    ])
    fixed_code = code
    for pattern, replacement, description in fixes:
        before_count = len(re.findall(pattern, fixed_code))
        fixed_code = re.sub(pattern, replacement, fixed_code)
        if before_count > 0:
            logger.info(f"Layout fix: {description} ({before_count} instances)")
    if has_comparison:
        final_molecules = re.findall(r'(\w+_final)\s*=\s*create_molecule_from_smiles', fixed_code)
        if len(final_molecules) >= 2:
            first_final = final_molecules[0]
            fixed_code = re.sub(
                rf'{first_final}\s*=\s*create_molecule_from_smiles\(([^)]*?)position\s*=\s*UP\s*\*\s*[0-9.]+',
                rf'{first_final} = create_molecule_from_smiles(\1position=LEFT * 2 + UP * 2.5',
                fixed_code, count=1
            )
            second_final = final_molecules[1]
            fixed_code = re.sub(
                rf'{second_final}\s*=\s*create_molecule_from_smiles\(([^)]*?)position\s*=\s*UP\s*\*\s*[0-9.]+',
                rf'{second_final} = create_molecule_from_smiles(\1position=RIGHT * 2 + UP * 2.5',
                fixed_code, count=1
            )
    return fixed_code


def fix_16_9_layout(code: str) -> str:
    fixes = [
        (r'title\.move_to\(UP \* [6-9](?:\.[0-9]+)?\)', 'title.move_to(UP * 3.5)', "Adjusting title for landscape"),
        (r'font_size\s*=\s*20(?![0-9])', 'font_size=24', "Increasing small fonts"),
        (r'font_size\s*=\s*24(?![0-9])', 'font_size=28', "Increasing medium fonts"),
        (r'font_size\s*=\s*3[2-9](?![0-9])', 'font_size=28', "Adjusting large fonts for landscape"),
    ]
    fixed_code = code
    for pattern, replacement, description in fixes:
        before_count = len(re.findall(pattern, fixed_code))
        fixed_code = re.sub(pattern, replacement, fixed_code)
        if before_count > 0:
            logger.info(f"Layout fix (16:9): {description} ({before_count} instances)")
    return fixed_code


def fix_square_layout(code: str) -> str:
    fixes = [
        (r'title\.move_to\(UP \* [6-9](?:\.[0-9]+)?\)', 'title.move_to(UP * 4)', "Adjusting title for square"),
        (r'create_molecule_from_smiles\(([^)]*?)position\s*=\s*UP\s*\*\s*[3-9](?:\.[0-9]+)?',
         r'create_molecule_from_smiles(\1position=UP * 1.5', "Adjusting molecule for square"),
        (r'(text[0-9]*)\.move_to\(DOWN \* [0-1](?:\.[0-9]+)?\)', r'\1.move_to(DOWN * 2.5)', "Adjusting text for square"),
        (r'create_molecule_from_smiles\(([^)]*?)scale\s*=\s*3\.0', r'create_molecule_from_smiles(\1scale=2.5', "Reducing scale for square"),
        (r'font_size\s*=\s*20(?![0-9])', 'font_size=26', "Increasing small fonts"),
    ]
    fixed_code = code
    for pattern, replacement, description in fixes:
        before_count = len(re.findall(pattern, fixed_code))
        fixed_code = re.sub(pattern, replacement, fixed_code)
        if before_count > 0:
            logger.info(f"Layout fix (square): {description} ({before_count} instances)")
    return fixed_code


def detect_text_overlaps(code: str) -> list:
    overlaps = []
    pattern = r'(\w+)\s*=\s*Text\([^)]+\)[^\n]*\.move_to\(([^)]+)\)'
    matches = list(re.finditer(pattern, code))
    position_map = {}
    for match in matches:
        var_name = match.group(1)
        position = match.group(2).strip()
        if position in position_map:
            prev_var = position_map[position]['var']
            prev_pos = position_map[position]['match_pos']
            current_pos = match.start()
            code_between = code[prev_pos:current_pos]
            if f'FadeOut({prev_var})' not in code_between:
                overlaps.append({
                    'prev_var': prev_var,
                    'current_var': var_name,
                    'position': position,
                    'line': code[:current_pos].count('\n') + 1,
                    'insert_pos': current_pos
                })
        position_map[position] = {'var': var_name, 'match_pos': match.end()}
    return overlaps


def fix_text_overlaps(code: str) -> str:
    overlaps = detect_text_overlaps(code)
    if not overlaps:
        return code
    logger.info(f"🔍 Found {len(overlaps)} text overlap(s)")
    overlaps = sorted(overlaps, key=lambda x: x['insert_pos'], reverse=True)
    fixed_code = code
    for overlap in overlaps:
        prev_var = overlap['prev_var']
        insert_pos = overlap['insert_pos']
        current_line_start = fixed_code[:insert_pos].rfind('\n') + 1
        current_line = fixed_code[current_line_start:insert_pos]
        indent = len(current_line) - len(current_line.lstrip())
        indent_str = ' ' * indent
        fadeout_line = f'\n{indent_str}self.play(FadeOut({prev_var}))\n{indent_str}'
        fixed_code = fixed_code[:insert_pos] + fadeout_line + fixed_code[insert_pos:]
        logger.info(f"✅ Added FadeOut({prev_var}) before {overlap['current_var']} at line {overlap['line']}")
    return fixed_code


def detect_comparison_scene(code: str) -> bool:
    indicators = [r'LEFT.*RIGHT.*create_molecule', r'mol1.*mol2', r'final.*comparison', r'side.by.side', r'compare']
    for indicator in indicators:
        if re.search(indicator, code, re.IGNORECASE | re.DOTALL):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────────────
# STAGE 1 — SOLUTION GENERATION (ChatGPT / GPT-4o)
# ─────────────────────────────────────────────────────────────────────────────────────

def build_solution_prompt(problem: str = None, language: str = "fi", duration: int = 60, image_url: str = None) -> str:
    image_section = f"""IMAGE CONTEXT:
The problem may include an image at this URL:
{image_url}
If the image contains diagrams, graphs, chemical setups, or formulas,
use it as additional context to understand or extract the question/problem.
""" if image_url else ""
    problem_section = f"TEXT PROBLEM:\n{problem}\n" if problem else "TEXT PROBLEM: (No text problem provided. Use image context if available.)\n"
    return f"""
{problem_section}
{image_section}
LANGUAGE: {language}
TARGET_DURATION: {duration} seconds

IMPORTANT:
- Use all available context (text and/or image) to understand the problem.
- Follow the system instructions for structured solutions exactly.
- Adapt explanation depth to TARGET_DURATION
- Prioritize correctness over verbosity
- Output JSON only in the required format
"""


def generate_verified_solution(problem: str, language: str = "fi", duration: int = 60) -> str:
    """Stage 1: Generate a correct, duration-aware solution using GPT-4o."""
    user_prompt = f"""
PROBLEM:
{problem}

LANGUAGE: {language}
TARGET_DURATION: {duration} seconds
"""
    response = _openai_sync.chat.completions.create(
        model="gpt-4o",
        temperature=0.0,
        messages=[
            {"role": "system", "content": CHATGPT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def generate_verified_solution_multimodal(
    problem: str | None = None,
    language: str = "fi",
    duration: int = 60,
    image_url: str | None = None,
) -> str:
    """Stage 1: GPT-4o with optional image input."""
    text_prompt = build_solution_prompt(problem=problem, language=language, duration=duration)
    user_content = [{"type": "text", "text": text_prompt}]
    if image_url:
        user_content.append({"type": "image_url", "image_url": {"url": image_url}})
    response = _openai_sync.chat.completions.create(
        model="gpt-4o",
        temperature=0.0,
        messages=[
            {"role": "system", "content": CHATGPT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw


# ─────────────────────────────────────────────────────────────────────────────────────
# SVG ASSET SYSTEM — copied verbatim from AnimLearn
# ─────────────────────────────────────────────────────────────────────────────────────

SVG_SYSTEM_PROMPT = """You are an SVG generator for scientific and physics diagrams used in educational videos.
Return ONLY raw SVG XML — no markdown, no backticks, no explanation, no preamble. Start your response with <svg.

MANDATORY RULES — violating any of these will cause the render to fail:
- First attribute on <svg>: viewBox="0 0 100 100" for square shapes, viewBox="0 0 200 100" for wide shapes (coils, arrows, resistors)
- stroke="white" on every path and shape — the background is black, white strokes only
- fill="none" on every path and shape — no filled regions
- stroke-width between 2 and 4
- No <text> or <tspan> elements — zero text
- No <rect> used as background — no background rectangles
- No black strokes (stroke="#000000", stroke="black") anywhere
- All shapes must be centered within the viewBox
- Keep paths minimal — clean engineering/scientific line art
- Output must be valid XML parseable by Python's xml.etree.ElementTree"""

SVG_ASSET_HINTS = {
    "resistor":         "A zigzag line symbol: horizontal line in, 4–5 sharp zigzag peaks, horizontal line out. Wide viewBox.",
    "capacitor":        "Two vertical parallel lines with horizontal leads connecting to them. Square viewBox.",
    "inductor_coil":    "A series of 4–5 semicircular arcs along a horizontal axis (like bumps). Wide viewBox.",
    "battery":          "Two vertical lines of different lengths (long=positive, short=negative) with horizontal leads. Square viewBox.",
    "ground_symbol":    "Horizontal line, below it a shorter line, below that an even shorter line — classic ground. Square viewBox.",
    "arrow_right":      "A clean right-pointing arrow: horizontal shaft with a triangular arrowhead. Wide viewBox.",
    "arrow_left":       "A clean left-pointing arrow. Wide viewBox.",
    "arrow_up":         "A clean upward-pointing arrow. Square viewBox.",
    "arrow_down":       "A clean downward-pointing arrow. Square viewBox.",
    "double_arrow":     "Arrow pointing both left and right. Wide viewBox.",
    "voltmeter":        "Circle with the letter V implied by a sine-wave arc inside. Square viewBox.",
    "ammeter":          "Circle with an arc inside implying current flow. Square viewBox.",
    "switch_open":      "A horizontal line with a gap and a diagonal line segment indicating open switch. Wide viewBox.",
    "switch_closed":    "A continuous horizontal line with a small circle contact point. Wide viewBox.",
    "diode":            "Triangle pointing right abutting a vertical line (anode→cathode). Wide viewBox.",
    "led":              "Diode symbol with two small arrows pointing away (light emission). Wide viewBox.",
    "transistor_npn":   "Vertical base line, two angled lines for collector and emitter, emitter has arrowhead. Square viewBox.",
    "op_amp":           "Triangle pointing right with + and − inputs on left side. Square viewBox.",
    "sine_wave":        "One full smooth sine wave cycle. Wide viewBox.",
    "spring":           "A series of angled zigzag lines forming a coil spring. Square viewBox.",
    "pulley":           "A circle with a horizontal line through the center (axle). Square viewBox.",
    "lens_convex":      "Two curved arcs forming a convex lens shape. Square viewBox.",
    "lens_concave":     "Two inward-curved arcs forming a concave lens. Square viewBox.",
    "prism":            "Equilateral triangle. Square viewBox.",
    "magnet_bar":       "Rectangle outline with N and L regions implied by a center dividing line. Wide viewBox.",
    "atom":             "A nucleus dot with 2–3 elliptical orbits around it. Square viewBox.",
    "force_arrow":      "A bold arrow with a clear thick shaft, suitable for force diagrams. Square viewBox.",
    "wave_packet":      "A localized oscillation — sine wave that grows then shrinks. Wide viewBox.",
    "electric_field":   "Several parallel horizontal arrows with field lines. Wide viewBox.",
    "magnetic_field":   "Circular arrows indicating field out of or into page. Square viewBox.",
    "car_side_view":    "Simple side-view of a car: rectangular body, two circles for wheels, windshield line. Wide viewBox.",
    "truck_side_view":  "Side-view of a truck: tall cab, long flat bed, four wheels. Wide viewBox.",
    "bicycle":          "Side-view bicycle: two wheels, frame triangle, handlebars, seat. Square viewBox.",
    "pendulum":         "A pivot bracket at top, a thin rod hanging down, circle weight at bottom. Square viewBox.",
    "pulley_system":    "Two circles (pulleys) with a rope looping around both, hanging weight. Square viewBox.",
    "gear":             "A circle with evenly-spaced rectangular teeth around the perimeter. Square viewBox.",
    "thermometer":      "A thin vertical rectangle with a circle at the bottom (bulb), fill level line inside. Square viewBox.",
    "piston":           "A rectangle (piston head) inside two parallel vertical lines (cylinder walls). Square viewBox.",
    "wave_transverse":  "A smooth sine wave showing one full transverse wave cycle. Wide viewBox.",
    "wave_longitudinal":"Alternating dense and sparse vertical lines showing compression regions. Wide viewBox.",
    "mirror_concave":   "A thick concave arc (opening to the right) with a flat back. Square viewBox.",
    "mirror_convex":    "A thick convex arc (bulging to the right) with a flat back. Square viewBox.",
    "eye_diagram":      "An almond/eye outline shape with iris circle and pupil dot inside. Square viewBox.",
    "nucleus":          "A dense cluster of small circles (protons/neutrons) packed together. Square viewBox.",
    "rocket":           "A rocket: pointed nose cone, cylindrical body, two delta fins at base. Square viewBox.",
    "planet_orbit":     "A large circle (star) at center, elliptical orbit path, small planet dot on orbit. Square viewBox.",
    "human_figure":     "A stick figure: circle head, line body, two arm lines, two leg lines. Square viewBox.",
    "lever_fulcrum":    "A horizontal bar resting on a triangle fulcrum, with load marks at ends. Wide viewBox.",
    "spring_coil":      "Repeated overlapping arcs forming a coil spring vertically. Square viewBox.",
    "traffic_light":    "Three circles stacked vertically (red top, yellow middle, green bottom) inside a rounded rectangle housing. Square viewBox.",
    "road_surface":     "Two horizontal parallel lines forming a road, with dashed center line. Wide viewBox.",
    "building":         "A rectangle outline (building body) with a grid of smaller rectangles (windows). Square viewBox.",
    "person_running":   "Stick figure mid-stride: circle head, angled body line, one arm forward, opposite leg forward. Square viewBox.",
    "person_standing":  "Stick figure upright: circle head, vertical body, two arms out slightly, two straight legs. Square viewBox.",
    "beaker":           "A trapezoidal outline (wider at top) with a small spout, liquid fill line inside. Square viewBox.",
    "flask_erlenmeyer": "A triangle-body flask with a narrow cylindrical neck and flat bottom. Square viewBox.",
    "test_tube":        "A narrow rectangle with a rounded bottom, angled slightly. Square viewBox.",
    "bunsen_burner":    "A vertical cylinder (barrel) with a small gas-inlet tube at the base, flame outline at top. Square viewBox.",
    "balance_scale":    "A central vertical rod, horizontal beam, two pans hanging from each end. Wide viewBox.",
    "light_bulb":       "Circle outline (glass globe) with two contact lines at the bottom and a small filament coil inside. Square viewBox.",
    "motor_symbol":     "Circle with an M implied by an arc inside and two lead lines. Square viewBox.",
    "transformer":      "Two coil symbols (inductor coils) side by side with a vertical center line. Wide viewBox.",
    "moon":             "A crescent shape: large filled circle with a slightly offset circle cut out. Square viewBox.",
    "sun_star":         "A circle with 8 short lines radiating outward evenly. Square viewBox.",
    "number_line":      "A horizontal arrow line with evenly spaced tick marks and a zero-mark at center. Wide viewBox.",
    "coordinate_axes":  "Two perpendicular arrow lines (x right, y up) with tick marks. Square viewBox.",
}

SVG_MAX_CHARS   = 10_000
SVG_MAX_RETRIES = 3

KEYWORD_SVG_MAP = {
    "bicycle": "bicycle", "bike": "bicycle", "cycling": "bicycle", "cyclist": "bicycle",
    "car": "car_side_view", "automobile": "car_side_view", "vehicle": "car_side_view",
    "truck": "truck_side_view", "lorry": "truck_side_view",
    "rocket": "rocket", "spacecraft": "rocket",
    "pendulum": "pendulum", "pulley": "pulley_system", "gear": "gear",
    "lever": "lever_fulcrum", "fulcrum": "lever_fulcrum", "piston": "piston",
    "spring": "spring_coil",
    "convex lens": "lens_convex", "concave lens": "lens_concave", "prism": "prism",
    "concave mirror": "mirror_concave", "convex mirror": "mirror_convex", "eye": "eye_diagram",
    "transverse wave": "wave_transverse", "longitudinal wave": "wave_longitudinal",
    "sine wave": "sine_wave",
    "atom": "atom", "nucleus": "nucleus", "planet": "planet_orbit", "orbit": "planet_orbit",
    "person": "human_figure", "human": "human_figure", "student": "human_figure",
    "walking": "person_standing", "running": "person_running", "runner": "person_running",
    "athlete": "person_running",
    "thermometer": "thermometer", "temperature": "thermometer",
    "traffic light": "traffic_light", "traffic_light": "traffic_light",
    "stoplight": "traffic_light", "stop light": "traffic_light",
    "road": "road_surface", "highway": "road_surface",
    "building": "building", "skyscraper": "building",
    "beaker": "beaker", "flask": "flask_erlenmeyer", "erlenmeyer": "flask_erlenmeyer",
    "test tube": "test_tube", "bunsen": "bunsen_burner",
    "balance": "balance_scale", "weighing": "balance_scale",
    "light bulb": "light_bulb", "lightbulb": "light_bulb", "lamp": "light_bulb",
    "motor": "motor_symbol", "transformer": "transformer",
    "moon": "moon", "sun": "sun_star", "star": "sun_star",
}


def prescan_svg_assets(text: str) -> list:
    """Keyword scan for real-world objects — fast, no AI call needed."""
    text_lower = text.lower()
    found = []
    seen = set()
    for keyword in sorted(KEYWORD_SVG_MAP.keys(), key=len, reverse=True):
        asset = KEYWORD_SVG_MAP[keyword]
        if asset not in seen and keyword in text_lower:
            found.append(asset)
            seen.add(asset)
    return found


def plan_svg_assets(verified_solution: str, subject: str) -> list:
    """Pass 1 — keyword prescan + AI planner → deduplicated list of asset names (max 5)."""
    MAX_TOTAL = 5
    prescanned = prescan_svg_assets(verified_solution)
    logger.info(f"🔍 SVG prescan found: {prescanned}")
    known_assets    = ", ".join(sorted(SVG_ASSET_HINTS.keys()))
    already_found   = ", ".join(prescanned) if prescanned else "none"
    remaining_slots = MAX_TOTAL - len(prescanned)
    ai_result = []
    if remaining_slots > 0:
        try:
            msg = _claude_sync.messages.create(
                model=_CLAUDE_MODEL,
                max_tokens=150,
                system=(
                    "You are planning SVG visual assets for an educational Manim animation.\n"
                    "Return ONLY a valid JSON array of snake_case asset names — no explanation, no markdown.\n\n"
                    "IMPORTANT — only request SVGs for objects too complex for Manim primitives.\n"
                    "Manim can already draw: Arrows, lines, force arrows → use Arrow()\n"
                    "                       Boxes, rectangles → use Rectangle()\n"
                    "                       Balls, circles → use Circle()\n"
                    "                       Ramps, inclined planes → use Polygon()\n\n"
                    "DO request SVGs for: circuit symbols, optical elements, mechanical assemblies, scientific diagrams, vehicles\n\n"
                    f"Already found by keyword scan (DO NOT repeat): {already_found}\n"
                    f"Known asset names (prefer these): {known_assets}\n"
                    f"Return max {remaining_slots} additional assets. Return [] if none needed."
                ),
                messages=[{"role": "user", "content": f"Subject: {subject}\n\nSolution:\n{verified_solution[:1500]}"}]
            )
            text = msg.content[0].text.strip()
            text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\n?```$", "", text).strip()
            result = json.loads(text)
            if isinstance(result, list):
                ai_result = [str(a).strip() for a in result if isinstance(a, str) and a.strip()]
        except Exception as e:
            logger.warning(f"⚠️  SVG AI planner failed: {e}")
    seen = set(prescanned)
    merged = list(prescanned)
    for asset in ai_result:
        if asset not in seen and asset in SVG_ASSET_HINTS:
            merged.append(asset)
            seen.add(asset)
    final = merged[:MAX_TOTAL]
    logger.info(f"🖼️  Final SVG plan: {final}")
    return final


def _strip_svg_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _validate_svg(svg_xml: str) -> tuple[bool, str]:
    if len(svg_xml) > SVG_MAX_CHARS:
        return False, f"SVG too large ({len(svg_xml)} chars, max {SVG_MAX_CHARS})"
    try:
        root = ET.fromstring(svg_xml)
    except ET.ParseError as e:
        return False, f"Invalid XML: {e}"
    svg_str_lower = svg_xml.lower()
    if "viewbox" not in svg_str_lower:
        return False, "Missing viewBox attribute"
    black_patterns = [
        'stroke="#000"', 'stroke="#000000"', 'stroke="black"',
        "stroke='#000'", "stroke='#000000'", "stroke='black'",
    ]
    for pat in black_patterns:
        if pat.lower() in svg_str_lower:
            return False, f"Black stroke detected: {pat}"
    tag_lower = root.tag.lower()
    ns = ""
    if "{" in tag_lower:
        ns = tag_lower[tag_lower.index("{"):tag_lower.index("}") + 1]
    for forbidden in [f"{ns}text", f"{ns}tspan"]:
        if root.find(f".//{forbidden}") is not None:
            return False, "Contains forbidden <text> or <tspan> elements"
    return True, ""


def r2_object_exists(key: str) -> bool:
    if r2_client is None:
        return False
    try:
        r2_client.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        return True
    except Exception:
        return False


def call_claude_svg(asset_name: str) -> str:
    """Call Claude to generate a single SVG. Returns stripped SVG XML string."""
    hint = SVG_ASSET_HINTS.get(asset_name, "")
    user_content = f"Generate a minimal clean SVG of: {asset_name}"
    if hint:
        user_content += f"\nShape description: {hint}"
    user_content += "\nRemember: white strokes only, fill=none, no text, valid XML, centered in viewBox."
    msg = _claude_sync.messages.create(
        model=_CLAUDE_MODEL,
        max_tokens=1000,
        system=SVG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return _strip_svg_markdown(msg.content[0].text)


def generate_svg_assets(svg_list: list) -> dict:
    """For each asset: check R2 cache, generate via Claude, upload. Returns {name: url}."""
    MAX_ASSETS = 5
    svg_urls = {}
    if r2_client is None:
        logger.warning("⚠️  R2 not configured — skipping SVG asset generation")
        return svg_urls

    def _presigned_url(key: str, expires: int = 3600) -> str:
        return r2_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expires,
        )

    for asset_name in svg_list[:MAX_ASSETS]:
        r2_key = f"svg_assets/{asset_name}.svg"
        if r2_object_exists(r2_key):
            logger.info(f"🖼️  SVG cache hit: {asset_name}")
            try:
                svg_urls[asset_name] = _presigned_url(r2_key)
            except Exception as e:
                logger.warning(f"⚠️  Could not presign cached SVG '{asset_name}': {e}")
            continue
        svg_xml = None
        for attempt in range(1, SVG_MAX_RETRIES + 1):
            try:
                logger.info(f"🎨 Generating SVG for '{asset_name}' (attempt {attempt}/{SVG_MAX_RETRIES})")
                candidate = call_claude_svg(asset_name)
                is_valid, reason = _validate_svg(candidate)
                if is_valid:
                    svg_xml = candidate
                    break
                else:
                    logger.warning(f"⚠️  SVG validation failed for '{asset_name}' attempt {attempt}: {reason}")
            except Exception as e:
                logger.warning(f"⚠️  Claude SVG call failed for '{asset_name}' attempt {attempt}: {e}")
        if svg_xml is None:
            logger.error(f"❌ All {SVG_MAX_RETRIES} attempts failed for '{asset_name}', skipping")
            continue
        try:
            r2_client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=r2_key,
                Body=svg_xml.encode("utf-8"),
                ContentType="image/svg+xml",
            )
            svg_urls[asset_name] = _presigned_url(r2_key)
            logger.info(f"✅ SVG uploaded: {r2_key}")
        except Exception as e:
            logger.error(f"❌ R2 upload failed for '{asset_name}': {e}")
    return svg_urls


# ─────────────────────────────────────────────────────────────────────────────────────
# HELPERS.PY INJECTION — copied verbatim from AnimLearn
# ─────────────────────────────────────────────────────────────────────────────────────

_HELPERS_CODE_CACHE: Optional[str] = None


def _load_helpers_code() -> str:
    global _HELPERS_CODE_CACHE
    if _HELPERS_CODE_CACHE is not None:
        return _HELPERS_CODE_CACHE
    helpers_path = Path(__file__).parent / "helpers.py"
    try:
        raw = helpers_path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        start = 0
        for i, line in enumerate(lines):
            if line.startswith("def ") or line.startswith("# ═"):
                start = i
                break
        _HELPERS_CODE_CACHE = "\n".join(lines[start:])
    except FileNotFoundError:
        logger.warning("⚠️ helpers.py not found — helper injection skipped")
        _HELPERS_CODE_CACHE = ""
    return _HELPERS_CODE_CACHE


def inject_helpers_inline(code: str) -> str:
    if "from helpers import" not in code and "import helpers" not in code:
        return code
    helpers_code = _load_helpers_code()
    if not helpers_code:
        return code
    code = re.sub(r"^(?:from helpers import[^\n]*|import helpers[^\n]*)\n", "", code, flags=re.MULTILINE)
    lines = code.split("\n")
    last_import = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            last_import = i
    injection = "\n\n# ── helpers.py injected inline ──\n" + helpers_code + "\n# ── end helpers ──\n"
    lines.insert(last_import + 1, injection)
    logger.info("🔧 helpers.py injected inline into generated scene")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────────────
# CODE FIXERS — copied verbatim from AnimLearn
# ─────────────────────────────────────────────────────────────────────────────────────

_INVALID_MANIM_COLORS = {
    "BROWN": "DARK_BROWN", "CYAN": "TEAL", "MAGENTA": "PINK", "VIOLET": "PURPLE",
    "NAVY": "DARK_BLUE", "BEIGE": "LIGHT_BROWN", "INDIGO": "PURPLE", "CORAL": "RED",
    "TURQUOISE": "TEAL", "LIME": "GREEN", "SILVER": "LIGHT_GRAY",
}


def fix_manim_colors(code: str) -> str:
    """Replace color constants not defined in Manim with valid equivalents."""
    for bad, good in _INVALID_MANIM_COLORS.items():
        code = re.sub(rf'\b{bad}\b', good, code)
    return code


def ensure_numpy_import(code: str) -> str:
    """Add 'import numpy as np' if numpy is used but not imported."""
    uses_numpy = bool(re.search(r'\bnp\.(linspace|cos|sin|tan|pi|array|zeros|ones|arange|sqrt|abs|dot|cross|linalg)\b', code))
    already_imported = bool(re.search(r'^import numpy', code, re.MULTILINE))
    if uses_numpy and not already_imported:
        code = re.sub(
            r'((?:^from manim[^\n]*\n|^import manim[^\n]*\n)+)',
            r'\1import numpy as np\n',
            code, count=1, flags=re.MULTILINE,
        )
    return code


def strip_invented_svg(code: str) -> str:
    """Remove get_svg() usage Claude invents when no SVG assets were provided."""
    code = re.sub(r"^import urllib\.request[^\n]*\n", "", code, flags=re.MULTILINE)
    code = re.sub(r"^import urllib\b[^\n]*\n",         "", code, flags=re.MULTILINE)
    code = re.sub(r"^import requests\b[^\n]*\n",        "", code, flags=re.MULTILINE)
    code = re.sub(r"^import os as _os[^\n]*\n",         "", code, flags=re.MULTILINE)
    code = re.sub(r"^import os\b[^\n]*\n",              "", code, flags=re.MULTILINE)
    code = re.sub(
        r"^def get_svg\b.*?(?=\n\n*(?:def |class )|\Z)",
        "", code, flags=re.MULTILINE | re.DOTALL,
    )
    code = re.sub(r"(\w+)\s*=\s*get_svg\([^\n]*\)", r"\1 = Dot(radius=0.01)", code)
    code = re.sub(r"^[^\n]*\bget_svg\([^\n]*\)[^\n]*\n", "", code, flags=re.MULTILINE)
    return code


def extract_scene_name(code: str) -> str:
    """Extract scene class name from Manim code."""
    code_lines = []
    for line in code.split('\n'):
        if '#' in line:
            line = line[:line.index('#')]
        code_lines.append(line)
    cleaned_code = '\n'.join(code_lines)
    patterns = [
        r'class\s+(\w+)\s*\(\s*VoiceoverScene\s*\)',
        r'class\s+(\w+)\s*\(\s*Scene\s*\)',
        r'class\s+(\w+)\s*\([^)]*Scene[^)]*\)',
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned_code, re.MULTILINE)
        if match:
            scene_name = match.group(1)
            logger.info(f"✅ Extracted scene name: {scene_name}")
            return scene_name
    fallback = re.search(r'class\s+(\w+)\s*\(', cleaned_code)
    if fallback:
        logger.warning(f"⚠️ Using fallback scene name: {fallback.group(1)}")
        return fallback.group(1)
    logger.error("❌ No scene class found, using default")
    return "GeneratedScene"


# ─────────────────────────────────────────────────────────────────────────────────────
# TWO-PASS CODE GENERATION — setup block first, animation beats second
# ─────────────────────────────────────────────────────────────────────────────────────

_PHASE2_SENTINEL = "# ═══ PHASE 2: ANIMATIONS START HERE ═══"


def _build_svg_section_for_prompt(svg_urls: dict) -> str:
    """Build the SVG assets section string for inclusion in prompts."""
    if not svg_urls:
        return ""
    svg_lines = "\n".join(
        f'  - {name}: get_svg("{name}", "{url}", height=0.8)'
        for name, url in svg_urls.items()
    )
    object_bindings = "\n".join(
        f'  - Any {name.replace("_", " ")} → MUST be get_svg("{name}", "{url}", height=0.8)'
        for name, url in svg_urls.items()
    )
    return f"""
══════════════════════════════════
AVAILABLE SVG ASSETS — MANDATORY USAGE
══════════════════════════════════
A helper function get_svg(name, url, height) is already defined at the top of the script.

OBJECT → SVG BINDING (NO EXCEPTIONS):
{object_bindings}

You MUST NOT draw any of the above objects using Rectangle(), Circle(), Polygon(), or any
other Manim primitive. The SVG IS the object.

EXACT CALL SYNTAX:
{svg_lines}
"""


def _extract_setup_names(setup_code: str) -> set:
    """Extract variable names assigned inside construct() from the setup block code."""
    names: set = set()
    try:
        tree = _ast_module.parse(setup_code)
        for node in _ast_module.walk(tree):
            if isinstance(node, _ast_module.FunctionDef) and node.name == "construct":
                for stmt in node.body:
                    if isinstance(stmt, _ast_module.Assign):
                        for t in stmt.targets:
                            if isinstance(t, _ast_module.Name):
                                names.add(t.id)
                    elif isinstance(stmt, _ast_module.AugAssign):
                        if isinstance(stmt.target, _ast_module.Name):
                            names.add(stmt.target.id)
                    elif isinstance(stmt, _ast_module.AnnAssign):
                        if isinstance(stmt.target, _ast_module.Name):
                            names.add(stmt.target.id)
    except Exception:
        pass
    return names


def _assemble_two_pass_code(setup_code: str, beats_code: str) -> str:
    """Concatenate setup block + animation beats at the PHASE 2 sentinel."""
    if _PHASE2_SENTINEL in setup_code:
        idx = setup_code.index(_PHASE2_SENTINEL) + len(_PHASE2_SENTINEL)
        # Keep any trailing content after the sentinel (shouldn't be any, but be safe)
        return setup_code[:idx] + "\n" + beats_code + setup_code[idx:]
    logger.warning("⚠️  PHASE 2 sentinel not found in setup block — concatenating directly")
    return setup_code + "\n\n" + beats_code


def _generate_setup_block_pass(
    verified_solution: str,
    video_script: str,
    storyboard_text: str,
    subject: str,
    language: str,
    duration: int,
    aspect_ratio: str,
    svg_urls: dict,
    system_prompt: str,
) -> str:
    """
    Pass 2a: Generate ONLY the setup block — imports, class definition,
    show_subtitle method, set_speech_service, and ALL Manim object definitions.
    Ends with the _PHASE2_SENTINEL comment. No animations included.
    """
    tts_import, tts_block = get_tts_prompt_blocks()
    tts_service_line = tts_block.strip().splitlines()[0]
    svg_section = _build_svg_section_for_prompt(svg_urls)

    prompt = f"""⚠️  YOUR ONLY TASK: Generate the SETUP BLOCK. No animations.

OUTPUT: A complete Python file that ends at (and including) the PHASE 2 sentinel.

REQUIRED STRUCTURE:
```
from manim import *
from manim_voiceover import VoiceoverScene
{tts_import}
import numpy as np

class SomeName(VoiceoverScene):
    def show_subtitle(self, text, duration=None):
        import textwrap
        wrapped = "\\n".join(textwrap.wrap(text, width=60))
        subtitle = Text(wrapped, font_size=18, color=WHITE, line_spacing=1.2).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(subtitle))
        if duration:
            self.wait(duration)
        return subtitle

    def construct(self):
        {tts_service_line}

        # ═══ PHASE 1: SETUP — define EVERY object before any animation ═══
        background = Rectangle(...)   # ← example
        # ... define ALL objects across ALL scenes here ...

        self.add(background)
        {_PHASE2_SENTINEL}
```

CRITICAL SETUP RULES:
1. Study EVERY scene in the storyboard and define EVERY Manim object mentioned
2. ALL objects must be defined here — not inside voiceover beats
3. ValueTracker + DecimalNumber pairs: include .add_updater() lambda in setup
4. VGroups: define sub-parts first, then assemble the VGroup from them
5. Composite objects (step panels, answer boxes, velocity displays): build fully here
6. Every object must have explicit positioning — no objects left at ORIGIN by default
7. self.add() only for background/grid; all other objects are added inside beats

DO NOT INCLUDE:
- Any `with self.voiceover(text=...):` blocks
- Any `self.play()` calls (only `self.add()` for initial scene setup is OK)
- Any animation logic of any kind

STORYBOARD (read EVERY scene — define EVERY object mentioned):
{storyboard_text}

{svg_section}

ASPECT RATIO: {aspect_ratio}  |  LANGUAGE: {language}  |  DURATION: {duration}s  |  SUBJECT: {subject}

VERIFIED SOLUTION (formula values and variable names — use these exactly):
{verified_solution[:700]}

Output ONLY valid Python code. No markdown fences. No explanation.
LAST LINE MUST BE EXACTLY (8 spaces indent):
        {_PHASE2_SENTINEL}
"""

    _stream_delays = [5, 15, 45, 135]
    message = None
    for _attempt, _delay in enumerate(_stream_delays[:4], 1):
        try:
            with _claude_sync.messages.stream(
                model=_CLAUDE_MODEL,
                max_tokens=8000,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                message = stream.get_final_message()
            break
        except Exception as _exc:
            _err = str(_exc)
            if ("overloaded_error" in _err or "overloaded" in _err.lower() or "529" in _err) and _attempt < 4:
                logger.warning(f"Claude overloaded (setup block attempt {_attempt}/4) — retrying in {_delay}s")
                time.sleep(_delay)
            else:
                raise
    if message is None:
        raise RuntimeError("Setup block generation failed after all retries")

    if message.stop_reason == "max_tokens":
        logger.warning("⚠️  Setup block hit max_tokens — object definitions may be incomplete")

    setup_code = message.content[0].text.strip()
    for fence in ("```python", "```"):
        if setup_code.startswith(fence):
            setup_code = setup_code[len(fence):].strip()
    if setup_code.endswith("```"):
        setup_code = setup_code[:-3].strip()

    if _PHASE2_SENTINEL not in setup_code:
        logger.warning("⚠️  PHASE 2 sentinel missing from setup block — appending it")
        setup_code += f"\n        {_PHASE2_SENTINEL}"

    n_defined = len(_extract_setup_names(setup_code))
    logger.info(f"✅ Setup block: {len(setup_code)} chars, {n_defined} objects defined")
    return setup_code


def _generate_animation_beats_pass(
    setup_code: str,
    verified_solution: str,
    video_script: str,
    storyboard_text: str,
    subject: str,
    language: str,
    duration: int,
    aspect_ratio: str,
    svg_urls: dict,
    system_prompt: str,
) -> str:
    """
    Pass 2b: Generate ONLY the animation beats (with self.voiceover(): blocks).
    Receives the complete setup block as context so it knows every defined variable.
    Returns indented code (8 spaces) to be appended after the sentinel.
    """
    defined_names = _extract_setup_names(setup_code)
    names_list = ", ".join(sorted(defined_names)) if defined_names else "(see setup block above)"
    svg_section = _build_svg_section_for_prompt(svg_urls)

    narration_section = ""
    if video_script and re.search(r'\[BEAT:', video_script):
        narration_section = f"""
══════════════════════════════════
NARRATION SCRIPT — USE AS VOICEOVER TEXT VERBATIM
══════════════════════════════════
Each [BEAT: ...] → one `with self.voiceover(text="..."):` block.
Narration AFTER the [BEAT] tag → verbatim voiceover text.

{video_script}
"""

    prompt = f"""⚠️  YOUR ONLY TASK: Generate the ANIMATION BEATS — `with self.voiceover():` blocks ONLY.

The setup block below is COMPLETE. Every Manim object is already defined and positioned.

━━━ SETUP BLOCK (reference — do NOT repeat any of this in your output) ━━━
```python
{setup_code}
```
━━━ END SETUP BLOCK ━━━

PRE-DEFINED VARIABLES available for animation:
{names_list}

YOUR OUTPUT: Only the animation beats, indented 8 spaces (inside construct()).

BEAT STRUCTURE — every voiceover block MUST have all of these:
1. `        with self.voiceover(text="...") as tracker:`
2. `            sub = self.show_subtitle("Same narration text")`
3. `            self.play(...)` — at least one real animation (not just self.wait)
4. `            self.wait(max(0.1, tracker.duration - 0.5))`
5. After the `with` block: `        self.play(FadeOut(sub))`

VARIABLE RULES:
✅ Use pre-defined variables by name — they exist and are already positioned
✅ `sub` (subtitle) — local temp var, create fresh in each beat
✅ Short temp vars inside lambdas / list comprehensions are fine
❌ DO NOT create new Manim objects (Rectangle, Text, Arrow, VGroup, etc.) inside beats
❌ DO NOT write imports, class definition, show_subtitle, construct() header, or setup code
❌ DO NOT redefine any setup variable

STORYBOARD (implement each scene in the listed order):
{storyboard_text}

{narration_section}

{svg_section}

VERIFIED SOLUTION (use values AS-IS — do not change any number):
{verified_solution[:500]}

ASPECT RATIO: {aspect_ratio}  |  LANGUAGE: {language}  |  DURATION: {duration}s  |  SUBJECT: {subject}

Output ONLY animation beats, indented 8 spaces.
Start directly with: `        with self.voiceover(`
No markdown fences. No imports. No class. No setup code.
"""

    _stream_delays = [5, 15, 45, 135]
    message = None
    for _attempt, _delay in enumerate(_stream_delays[:4], 1):
        try:
            with _claude_sync.messages.stream(
                model=_CLAUDE_MODEL,
                max_tokens=16000,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                message = stream.get_final_message()
            break
        except Exception as _exc:
            _err = str(_exc)
            if ("overloaded_error" in _err or "overloaded" in _err.lower() or "529" in _err) and _attempt < 4:
                logger.warning(f"Claude overloaded (animation beats attempt {_attempt}/4) — retrying in {_delay}s")
                time.sleep(_delay)
            else:
                raise
    if message is None:
        raise RuntimeError("Animation beats generation failed after all retries")

    if message.stop_reason == "max_tokens":
        logger.warning("⚠️  Animation beats hit max_tokens — response may be truncated")

    beats_code = message.content[0].text.strip()
    for fence in ("```python", "```"):
        if beats_code.startswith(fence):
            beats_code = beats_code[len(fence):].strip()
    if beats_code.endswith("```"):
        beats_code = beats_code[:-3].strip()

    logger.info(f"✅ Animation beats: {len(beats_code)} chars")
    return beats_code


# ─────────────────────────────────────────────────────────────────────────────────────
# FULL MANIM PIPELINE — synchronous inner function (adapted from AnimLearn verbatim)
# ─────────────────────────────────────────────────────────────────────────────────────

def _generate_solution_sync(
    prompt: str,
    language: str = "en",
    duration: int = 60,
) -> dict:
    """
    Stage 1 only — GPT-4o solution + transcript.
    Returns solution_data dict (no Manim code).
    """
    verified_solution_raw = generate_verified_solution(
        problem=prompt, language=language, duration=duration
    )
    if isinstance(verified_solution_raw, str):
        cleaned = verified_solution_raw.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*",     "", cleaned)
        cleaned = re.sub(r"\s*```$",     "", cleaned).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("⚠️  GPT solution JSON parse failed — wrapping as plain text")
            data = {
                "structured_solution": cleaned,
                "transcript_markdown": cleaned,
                "subject": "general",
                "tags": [],
            }
    else:
        data = verified_solution_raw if isinstance(verified_solution_raw, dict) else {}

    verified_solution   = data.get("structured_solution") or data.get("solution", "")
    transcript_markdown = data.get("transcript_markdown") or verified_solution
    video_script        = data.get("video_script") or transcript_markdown
    subject             = data.get("subject", "general")
    tags                = data.get("tags", [])

    return {
        "verified_solution":   verified_solution,
        "transcript_markdown": transcript_markdown,
        "video_script":        video_script,
        "subject":             subject,
        "tags":                tags,
    }


def _generate_manim_code_enhanced_sync(
    prompt: str,
    language: str = "en",
    duration: int = 60,
    aspect_ratio: str = "16:9",
    _solution_data: Optional[dict] = None,   # injected for retry path (skips Stage 1)
) -> dict:
    """
    Full AnimLearn pipeline (synchronous):
      Stage 1   — GPT-4o verified solution  (skipped when _solution_data provided)
      Stage 1.5 — SVG planning + generation
      Stage 1.75 — Animation storyboard (Claude)
      Stage 2a  — Claude setup block: all Manim object definitions (no animations)
      Stage 2b  — Claude animation beats: voiceover blocks using pre-defined objects
      Stage 3   — Critic loop (Claude)
      Post      — AST undefined-name check + fix pass + syntax check
    """
    # ─── Stage 1 — GPT-4o solution (or use injected solution for retry) ──────
    if _solution_data is not None:
        verified_solution   = _solution_data.get("verified_solution", "")
        transcript_markdown = _solution_data.get("transcript_markdown", "")
        video_script        = _solution_data.get("video_script") or transcript_markdown
        promptSubject       = _solution_data.get("subject", "general")
        promptTags          = _solution_data.get("tags", [])
    else:
        sol = _generate_solution_sync(prompt, language, duration)
        verified_solution   = sol["verified_solution"]
        transcript_markdown = sol["transcript_markdown"]
        video_script        = sol["video_script"]
        promptSubject       = sol["subject"]
        promptTags          = sol.get("tags", [])

    # ─── Stage 1.5 — SVG planning + generation ────────────────────────────────
    svg_list = plan_svg_assets(verified_solution, promptSubject)
    svg_urls = {}
    if svg_list:
        logger.info(f"🖼️  SVG plan: {svg_list}")
        svg_urls = generate_svg_assets(svg_list)
        logger.info(f"🖼️  SVGs ready: {list(svg_urls.keys())}")

    # ─── Stage 1.75 — Animation storyboard ────────────────────────────────────
    storyboard_text = ""
    beat_markers = re.findall(r'\[BEAT:\s*([^\]]+)\]', video_script)
    try:
        if beat_markers:
            full_beat_lines = re.findall(r'\[BEAT:\s*([^\]]+)\]', video_script)
            beat_list = "\n".join(f"{i+1}. {b.strip()}" for i, b in enumerate(full_beat_lines))
            svg_binding = ""
            if svg_urls:
                svg_binding = "\n\nSVG ASSET BINDING (MANDATORY):\n"
                svg_binding += "These SVG assets are pre-generated. For every beat that involves the objects below, you MUST specify get_svg() — NEVER use Rectangle/Circle as a substitute:\n"
                for name in svg_urls:
                    svg_binding += f'  - Any {name.replace("_", " ")} → write: USE get_svg("{name}", url, height=X)\n'
                svg_binding += "If a beat involves any of these objects, your direction MUST say 'USE get_svg(...)' explicitly."
            storyboard_prompt = f"""You are a Manim animation director. The narration script defines these visual beats (with emotion tags):

{beat_list}

SUBJECT: {promptSubject}
ASPECT RATIO: {aspect_ratio}
DURATION: {duration} seconds
{svg_binding}

For EACH beat, provide specific Manim implementation direction:
- MANIM OBJECTS: exact class names (Polygon, Arrow, SVGMobject, DecimalNumber, MathTex, etc.)
  → If an SVG asset exists for the object, write: USE get_svg("name", url, height=X)
  → Do NOT suggest Rectangle/Circle for any object that has an SVG asset
- ANIMATION: exact animation call — MUST match the emotion tag:
    curious   → FadeIn with shift, DrawBorderThenFill, slow Create
    building  → GrowArrow, AnimationGroup(lag_ratio=0.25), Write
    surprise  → Flash, color change, sudden Indicate
    pivot     → Circumscribe, Indicate(scale_factor=1.8), brief pause
    reveal    → Circumscribe + color highlight + DecimalNumber pop
    satisfy   → FadeOut clutter → clean final state, slow fade
    dramatic  → MoveAlongPath + simultaneous arrow shift, rate_func=smooth
- MOTION: if object moves — start pos, end pos, rate_func
- GEOMETRY: for slopes — exact direction vectors

Output as a numbered list. No code — precise direction notes only.

MANDATORY PHYSICS RULES:
- Main object MUST physically move in at least one beat
- Force arrows: GrowArrow() only, NEVER Create()
- Force arrows shift() WITH the object in the same play() call
- Normal force perpendicular to surface: normal_dir = [sin θ, cos θ, 0]
- Gravity always straight DOWN: direction=[0,-1,0]"""
        else:
            num_scenes = max(2, min(duration // 15, 12))
            svg_binding_scratch = ""
            if svg_urls:
                svg_binding_scratch = "\nSVG ASSET BINDING (MANDATORY):\n"
                svg_binding_scratch += "Use get_svg() for these — NEVER substitute with Rectangle/Circle:\n"
                for name in svg_urls:
                    svg_binding_scratch += f'  - {name.replace("_", " ")} → USE get_svg("{name}", url, height=X)\n'
            storyboard_prompt = f"""You are an animation storyboard director for a {duration}-second educational Manim video.

TOPIC: {verified_solution[:800]}

SUBJECT: {promptSubject}
ASPECT RATIO: {aspect_ratio}
{svg_binding_scratch}
Write a storyboard with exactly {num_scenes} scenes covering a Hook → Build → Reveal → So What narrative arc.
For each scene, describe:
1. SCENE NAME (short label)
2. WHAT APPEARS: which Manim objects are drawn or faded in
3. WHAT MOVES: which object moves, along what path
4. FORCE ARROWS: which arrows appear, exact geometric directions
5. VOICEOVER CUE: one sentence of narration

MANDATORY RULES:
- Main object MUST physically move in at least one scene
- Force arrows use GrowArrow(), shift() with object in same play() call
- Normal force is perpendicular to slope surface, NOT straight up
- Gravity is always straight DOWN"""

        storyboard_response = claude_with_retry(
            _claude_sync.messages.create,
            model=_CLAUDE_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": storyboard_prompt}]
        )
        storyboard_text = storyboard_response.content[0].text.strip()
        logger.info(f"📋 Storyboard ready: {len(storyboard_text)} chars")
    except Exception as sb_err:
        logger.warning(f"⚠️ Storyboard generation failed (non-fatal): {sb_err}")
        storyboard_text = ""

    # ─── Stage 2 — Two-pass code generation ──────────────────────────────────
    # Pass 2a: SETUP BLOCK — generate all object definitions (no animations)
    # Pass 2b: ANIMATION BEATS — generate voiceover blocks using pre-defined objects
    # This eliminates NameErrors from objects referenced before they are defined.
    system_prompt = _build_system_prompt(promptSubject, aspect_ratio, language)

    logger.info("[pipeline] Stage 2a: Generating setup block")
    setup_code = _generate_setup_block_pass(
        verified_solution=verified_solution,
        video_script=video_script,
        storyboard_text=storyboard_text,
        subject=promptSubject,
        language=language,
        duration=duration,
        aspect_ratio=aspect_ratio,
        svg_urls=svg_urls,
        system_prompt=system_prompt,
    )

    logger.info("[pipeline] Stage 2b: Generating animation beats")
    beats_code = _generate_animation_beats_pass(
        setup_code=setup_code,
        verified_solution=verified_solution,
        video_script=video_script,
        storyboard_text=storyboard_text,
        subject=promptSubject,
        language=language,
        duration=duration,
        aspect_ratio=aspect_ratio,
        svg_urls=svg_urls,
        system_prompt=system_prompt,
    )

    response_text = _assemble_two_pass_code(setup_code, beats_code)
    logger.info(f"[pipeline] Two-pass assembly: {len(response_text)} chars")

    response_text = fix_molecular_layout(response_text, aspect_ratio)
    logger.info(f"✅ Layout fixer applied for {aspect_ratio}")

    # Two-pass output has no ###METADATA### — use Stage 1 values directly
    code             = response_text
    subject          = promptSubject
    tags             = promptTags
    estimated_duration = duration

    # Strip markdown fences
    if code.startswith("```python"):
        code = code.replace("```python", "").replace("```", "").strip()
    elif code.startswith("```"):
        code = code.replace("```", "").strip()

    # Clean up code — keep only Manim-relevant parts
    if "\n\n" in code:
        parts = code.split("\n\n")
        code_parts = [
            part for part in parts
            if any(kw in part for kw in ["from manim", "class ", "def ", "self."])
        ]
        code = "\n\n".join(code_parts)

    # Safety patches
    code = fix_manim_colors(code)
    code = ensure_numpy_import(code)
    code = re.sub(r'VGroup\(\s*\*\s*self\.mobjects\s*\)', 'Group(*self.mobjects)', code)

    # Hoist show_subtitle if defined as inner function inside construct()
    if re.search(r'^        def show_subtitle\(self', code, re.MULTILINE):
        inner_match = re.search(
            r'^        (def show_subtitle\(self.*?)(?=\n        [^\s]|\n    def |\Z)',
            code, re.MULTILINE | re.DOTALL
        )
        if inner_match:
            inner_block = inner_match.group(1)
            dedented = re.sub(r'^    ', '', inner_block, flags=re.MULTILINE)
            code = code.replace('        ' + inner_block, '')
            code = re.sub(
                r'(    def construct\(self\):)',
                '    ' + dedented.strip() + '\n\n    \\1',
                code, count=1
            )
            logger.info("🔧 Auto-fixed: show_subtitle hoisted to class method")

    # SVG helper injection / strip
    if not svg_urls:
        code = strip_invented_svg(code)
    if svg_urls:
        code = re.sub(
            r"^def get_svg\(.*?(?=\n(?:def |class |\Z))",
            "", code, flags=re.MULTILINE | re.DOTALL,
        )
        code = re.sub(r"^import urllib\.request[^\n]*\n", "", code, flags=re.MULTILINE)
        code = re.sub(r"^import os as _os[^\n]*\n",        "", code, flags=re.MULTILINE)
        code = re.sub(r"^import requests\n", "", code, flags=re.MULTILINE)
        code = re.sub(r"^import os\n", "",     code, flags=re.MULTILINE)
        svg_helper = (
            "import urllib.request, os as _os\n\n"
            "def get_svg(name, url, height=0.8):\n"
            "    \"\"\"Download SVG from R2 and return as a sized SVGMobject.\"\"\"\n"
            "    tmp = f\"/tmp/svg_{name}.svg\"\n"
            "    if not _os.path.exists(tmp):\n"
            "        urllib.request.urlretrieve(url, tmp)\n"
            "    return SVGMobject(tmp).set_height(height)\n\n"
        )
        lines = code.split("\n")
        last_import = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                last_import = i
        lines.insert(last_import + 1, "\n" + svg_helper)
        code = "\n".join(lines)

    # ─── Stage 3 — Critic loop ────────────────────────────────────────────────
    try:
        critic_prompt = f"""You are a Manim animation quality critic. Review the code below and fix any animation quality issues.

ANIMATION QUALITY CHECKLIST — check each item:

1. OBJECT MOTION: Does the main object physically MOVE at least once?
   Fix: Add MoveAlongPath or .animate.move_to() for the main object

2. FORCE ARROWS: Are force arrows revealed with GrowArrow() (not Create())?
   Fix: Replace Create(arrow) → GrowArrow(arrow) for ALL force/vector arrows

3. ARROWS FOLLOW OBJECT: When the object moves, do ALL its force arrows shift() in the SAME play() call?
   Fix: Group arrows into VGroup(...) and add .animate.shift(delta) to the motion play()

4. SLOPE GEOMETRY: If there's an inclined plane, are forces geometrically correct?
   Normal force must be PERPENDICULAR to slope surface (not straight UP)
   Friction must be ALONG the slope surface (not horizontal)

5. STATIC TEXT DUMPS: Does every voiceover block have a real animation (not just self.wait())?
   Fix: Add at least one Create/FadeIn/GrowArrow/Indicate per voiceover block

6. INDICATE KEY TERMS: After showing a formula, does the code Indicate() the key term?

7. RATE FUNCTIONS: Do motion animations use meaningful rate functions?

8. VGROUP CRASH: Does any line use VGroup(*self.mobjects)?
   Fix: Replace EVERY occurrence with Group(*self.mobjects)

9. SVG AUDIT: SVG assets available: {list(svg_urls.keys()) if svg_urls else 'none'}
   If any named SVG object is drawn as a primitive shape, replace it with get_svg().

10. ZERO-LENGTH LINE/DASHEDLINE CRASH: Guard with length check before every DashedLine/Line:
    _s, _e = np.array([...]), np.array([...])
    if np.linalg.norm(_e - _s) > 0.01:
        dash = DashedLine(_s, _e, ...)

11. NEGATIVE WAIT DURATION: Replace self.wait(tracker.duration - X) with self.wait(max(0.1, tracker.duration - X))

12. UNDEFINED VARIABLES (CRITICAL — most common crash cause):
    Scan every name passed to self.play(), FadeIn(), FadeOut(), GrowArrow(),
    VGroup(), AnimationGroup(), Indicate(), Circumscribe(), MoveAlongPath(), etc.
    Each name MUST be assigned BEFORE the first `with self.voiceover(...)` block.

    Steps to check:
    a) Find the first `with self.voiceover(` line.
    b) For every animation call from that point on, list all names used.
    c) Verify each name appears as `name = ...` ABOVE the first voiceover block.
    d) Any missing name → add its definition in the SETUP BLOCK at the top of construct().

    Common patterns that cause NameError:
    - Object defined inside one voiceover beat, referenced in a later beat
    - VGroup assembled from parts that are not yet defined
    - Composite objects (cup, steam_lines, diagram_group, laws_summary,
      crystal_dots, final_cup, etc.) used in animations but never built
    - make_steam / helper functions defined AFTER the point where their
      result is used

    Fix: Insert a SETUP BLOCK at the top of construct() (after set_speech_service)
    that assigns ALL missing objects before the first voiceover block.

IMPORTANT: Only fix real problems. Do NOT restructure. Return ONLY the corrected Python code (no markdown fences).
If the code is already good, return it unchanged.

CODE TO REVIEW:
```python
{code}
```"""

        critic_response = claude_with_retry(
            _claude_sync.messages.create,
            model=_CLAUDE_MODEL,
            max_tokens=16000,
            messages=[{"role": "user", "content": critic_prompt}]
        )
        critic_text = critic_response.content[0].text.strip()
        if critic_text.startswith("```python"):
            critic_text = critic_text[len("```python"):].strip()
        if critic_text.startswith("```"):
            critic_text = critic_text[3:].strip()
        if critic_text.endswith("```"):
            critic_text = critic_text[:-3].strip()
        try:
            compile(critic_text, "<critic>", "exec")
            if len(critic_text) > 100:
                code = critic_text
                logger.info(f"✅ Critic loop applied: {len(code)} chars")
            else:
                logger.warning("⚠️ Critic returned too-short code — keeping original")
        except SyntaxError as critic_syn:
            logger.warning(f"⚠️ Critic output has syntax error — keeping original: {critic_syn}")
    except Exception as critic_err:
        logger.warning(f"⚠️ Critic loop failed (non-fatal): {critic_err}")

    # Re-apply safety patches after critic
    code = re.sub(r'VGroup\(\s*\*\s*self\.mobjects\s*\)', 'Group(*self.mobjects)', code)
    code = fix_manim_colors(code)
    code = ensure_numpy_import(code)

    # ─── AST undefined-name check + targeted fix pass ─────────────────────
    try:
        undefined = find_undefined_in_construct(code)
        if undefined:
            logger.warning(f"⚠️  Undefined names in construct(): {undefined}")
            code = fix_missing_definitions_pass(code, undefined)
            # Re-apply patches after fix
            code = re.sub(r'VGroup\(\s*\*\s*self\.mobjects\s*\)', 'Group(*self.mobjects)', code)
            code = fix_manim_colors(code)
            code = ensure_numpy_import(code)
            # Verify fix actually resolved the issues
            still_undefined = find_undefined_in_construct(code)
            if still_undefined:
                logger.warning(f"⚠️  Still undefined after fix pass: {still_undefined}")
            else:
                logger.info("✅ All undefined names resolved by fix pass")
        else:
            logger.info("✅ AST check passed — no undefined names in construct()")
    except Exception as undef_err:
        logger.warning(f"⚠️  AST undefined-name check failed (non-fatal): {undef_err}")

    # Inject helpers inline (after critic so critic sees compact code)
    code = inject_helpers_inline(code)

    # Syntax validation
    try:
        compile(code, "<generated>", "exec")
    except SyntaxError as syn_err:
        raise ValueError(f"Generated code has a syntax error (likely truncated): {syn_err}")

    scene_name = extract_scene_name(code)
    logger.info(f"✅ Generated code: {len(code)} chars | scene: {scene_name} | subject: {subject}")

    return {
        "code": code,
        "scene_name": scene_name,
        "subject": subject,
        "tags": tags,
        "estimated_duration": estimated_duration,
        "transcript_markdown": transcript_markdown,
        "video_script": video_script,
        "verified_solution": verified_solution,
        "svg_urls": svg_urls,
    }


# ─────────────────────────────────────────────────────────────────────────────────────
# PUBLIC ASYNC API
# ─────────────────────────────────────────────────────────────────────────────────────

async def generate_manim_code_enhanced(
    prompt: str,
    language: str = "en",
    duration: int = 60,
    aspect_ratio: str = "16:9",
) -> dict:
    """
    Async wrapper around the synchronous AnimLearn pipeline.
    Runs the CPU/IO-bound pipeline in a thread executor so it doesn't block the event loop.
    """
    return await asyncio.to_thread(
        _generate_manim_code_enhanced_sync,
        prompt, language, duration, aspect_ratio,
    )


def trigger_cloud_run_vm(video_id: int, svg_urls: dict = None):
    """
    Trigger GCP Cloud Run renderer — same payload as AnimLearn.
    Cloud Run reads generated_code + scene_name from the videos table.
    """
    if not CLOUD_RUN_URL:
        logger.warning("⚠️  CLOUD_RUN_VIDEO_URL not set — skipping Cloud Run trigger")
        return
    payload = {"job_id": video_id, "svg_urls": svg_urls or {}}
    headers = {
        "Authorization": f"Bearer {RAILWAY_CALL_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(CLOUD_RUN_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"🚀 Cloud Run triggered for video {video_id}")
    except Exception as e:
        logger.error(f"❌ Failed to trigger Cloud Run for video {video_id}: {e}", exc_info=True)


# Alias used by routers/videos.py
_trigger_video_generation = trigger_cloud_run_vm


# ─────────────────────────────────────────────────────────────────────────────────────
# SPLIT-PIPELINE PUBLIC API  (used by retry endpoint)
# ─────────────────────────────────────────────────────────────────────────────────────

async def generate_solution_only(
    prompt: str,
    language: str = "en",
    duration: int = 60,
) -> dict:
    """
    Async wrapper for Stage 1 only (GPT-4o solution + transcript).
    Returns solution_data dict — no Manim code generated.
    """
    return await asyncio.to_thread(_generate_solution_sync, prompt, language, duration)


async def generate_manim_from_solution(
    solution_data: dict,
    language: str = "en",
    duration: int = 60,
    aspect_ratio: str = "16:9",
) -> dict:
    """
    Async wrapper for Stage 2+ only (SVG → storyboard → Manim → critic → AST fix).
    Skips Stage 1 (GPT-4o) — uses pre-computed solution_data from generate_solution_only().
    """
    return await asyncio.to_thread(
        _generate_manim_code_enhanced_sync,
        "",            # prompt unused when _solution_data is provided
        language, duration, aspect_ratio,
        solution_data,
    )
