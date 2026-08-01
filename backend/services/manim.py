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
  strip_invalid_tex_weight(code) → str
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
# Timeout: 600 s per request — Manim code-gen calls can produce up to 16 000 tokens
# (~400 s at 40 tok/s). 120 s was too short and caused 499 client-disconnect errors
# on the Anthropic side for setup-block / animation-beats / critic passes.
_claude_sync = anthropic.Anthropic(
    api_key=settings.ANTHROPIC_API_KEY,
    timeout=600.0,
)
_openai_sync = _openai_module.OpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=120.0,
)

# ── Models for Manim pipeline ────────────────────────────────────────────────────────
# All generation passes (storyboard, SVG, setup block, beats) — Opus for quality
_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL_NAME", "claude-opus-5")
# Repair passes only (critic, fix, improve) — Sonnet at 64K to avoid truncation
_CLAUDE_MODEL_FAST = os.getenv("CLAUDE_MODEL_FAST", "claude-sonnet-5")

# ── Alternate video generation provider ──────────────────────────────────────────────
# Set VIDEO_MODEL_PROVIDER=gemini + GEMINI_API_KEY to route setup block + beats to Gemini.
# All other passes (storyboard, SVG, critic, fix) remain on Claude regardless.
_VIDEO_MODEL_PROVIDER = settings.VIDEO_MODEL_PROVIDER  # "claude" | "gemini"
_GEMINI_MODEL_NAME    = settings.GEMINI_MODEL_NAME      # default: "gemini-2.5-pro"
_gemini_client = None       # google.genai.Client instance, set below if provider=gemini
_gemini_types  = None       # google.genai.types module reference
if _VIDEO_MODEL_PROVIDER == "gemini":
    try:
        from google import genai as _google_genai_mod
        from google.genai import types as _google_genai_types
        _gemini_client = _google_genai_mod.Client(api_key=settings.GEMINI_API_KEY)
        _gemini_types  = _google_genai_types
        # List available models so the right GEMINI_MODEL_NAME can be chosen
        try:
            _all_models = list(_gemini_client.models.list())
            _model_names = [getattr(m, "name", str(m)) for m in _all_models]
            logger.info(f"[gemini] Available models ({len(_model_names)} total): {_model_names}")
        except Exception as _list_err:
            logger.warning(f"[gemini] Could not list models: {type(_list_err).__name__}: {_list_err}")
        logger.info(f"[video] Generation provider: Gemini — model={_GEMINI_MODEL_NAME}")
    except Exception as _gemini_init_err:
        logger.error(f"Gemini init failed ({_gemini_init_err}) — falling back to Claude")
        _VIDEO_MODEL_PROVIDER = "claude"
else:
    logger.info(f"[video] Generation provider: Claude — model={_CLAUDE_MODEL}")


def _first_text(message) -> str:
    """Return text from the first TextBlock, skipping ThinkingBlocks (claude-sonnet-5+)."""
    for block in (message.content or []):
        if getattr(block, "text", None) is not None:
            return block.text
    return ""


def _call_generation_pass(system_prompt: str, user_prompt: str, max_tokens: int, pass_name: str) -> str:
    """
    Route a heavy generation pass (setup block, beats) to Claude or Gemini
    based on VIDEO_MODEL_PROVIDER. Returns raw text (no fence stripping).
    """
    if _VIDEO_MODEL_PROVIDER == "gemini" and _gemini_client is not None:
        return _call_gemini_generation(system_prompt, user_prompt, max_tokens, pass_name)
    return _call_claude_generation(system_prompt, user_prompt, max_tokens, pass_name)


def _call_claude_generation(system_prompt: str, user_prompt: str, max_tokens: int, pass_name: str) -> str:
    """Claude streaming generation with exponential-backoff retry."""
    _stream_delays = [5, 15, 45, 135]
    message = None
    for _attempt, _delay in enumerate(_stream_delays[:4], 1):
        try:
            with _claude_sync.messages.stream(
                model=_CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_prompt}]
            ) as stream:
                message = stream.get_final_message()
            _cu = getattr(message, "usage", None)
            if _cu:
                logger.info(
                    f"[cache] {pass_name} — "
                    f"write={getattr(_cu,'cache_creation_input_tokens',0)} "
                    f"read={getattr(_cu,'cache_read_input_tokens',0)}"
                )
            break
        except Exception as _exc:
            _err = str(_exc)
            if ("overloaded_error" in _err or "overloaded" in _err.lower() or "529" in _err) and _attempt < 4:
                logger.warning(f"Claude overloaded ({pass_name} attempt {_attempt}/4) — retrying in {_delay}s")
                time.sleep(_delay)
            else:
                raise
    if message is None:
        raise RuntimeError(f"{pass_name} (Claude) failed after all retries")
    if message.stop_reason == "max_tokens":
        logger.warning(f"⚠️  {pass_name} hit max_tokens — output may be incomplete")
    return _first_text(message).strip()


def _call_gemini_generation(system_prompt: str, user_prompt: str, max_tokens: int, pass_name: str) -> str:
    """Gemini generation via google-genai SDK with retry."""
    _retry_delays = [5, 15, 45]
    last_exc = None
    for _attempt, _delay in enumerate([0] + _retry_delays, 1):
        if _attempt > 1:
            logger.warning(f"Gemini retry ({pass_name} attempt {_attempt}/4) in {_delay}s")
            time.sleep(_delay)
        try:
            response = _gemini_client.models.generate_content(
                model=_GEMINI_MODEL_NAME,
                contents=user_prompt,
                config=_gemini_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=min(max_tokens, 65536),
                    temperature=1.0,
                ),
            )
            candidate = response.candidates[0]
            finish = getattr(candidate.finish_reason, "name", str(candidate.finish_reason))
            if finish == "MAX_TOKENS":
                logger.warning(f"⚠️  {pass_name} (Gemini) hit MAX_TOKENS — output may be incomplete")
            usage = getattr(response, "usage_metadata", None)
            if usage:
                logger.info(
                    f"[gemini] {pass_name} — "
                    f"in={getattr(usage,'prompt_token_count',0)} "
                    f"out={getattr(usage,'candidates_token_count',0)} "
                    f"finish={finish}"
                )
            return response.text.strip()
        except Exception as _exc:
            last_exc = _exc
            _exc_str = str(_exc)
            logger.error(f"Gemini error ({pass_name} attempt {_attempt}/4): {type(_exc).__name__}: {_exc_str[:300]}")
            # Don't retry billing/auth/model errors — they won't resolve themselves
            if any(code in _exc_str for code in ("RESOURCE_EXHAUSTED", "prepayment", "API_KEY_INVALID", "PERMISSION_DENIED", "NOT_FOUND")):
                logger.error(f"Gemini fatal error — not retrying: {_exc_str[:200]}")
                break
            if _attempt >= 4:
                break
    raise RuntimeError(f"{pass_name} (Gemini) failed after all retries: {last_exc}")

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
    # color utilities
    'ManimColor','color_gradient','interpolate_color',
    # math
    'PI','TAU','DEGREES','INF','config',
    'np',
    # Manim mobjects
    'Text','MathTex','Tex','MarkupText','Paragraph','BulletedList',
    'Circle','Rectangle','Square','Ellipse','Triangle','Polygon','RoundedRectangle',
    'Line','DashedLine','DashedVMobject','Arrow','DoubleArrow','CurvedArrow','TangentLine',
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
    # Bohr atom helper (injected for chemistry videos)
    'draw_bohr_atom','ATOM_CONFIGS',
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
            model=_CLAUDE_MODEL_FAST,
            max_tokens=64000,
            messages=[{"role": "user", "content": fix_prompt}],
        )
        fixed = _first_text(response).strip()
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
            # Guard: remove any `X = X` self-assignments the model may have
            # generated (e.g. `ManimColor = ManimColor`).  These crash with
            # UnboundLocalError because Python treats the LHS as a new local
            # before evaluating the RHS.
            fixed = _remove_self_assignments(fixed)
            logger.info(f"✅ Fix pass applied ({len(fixed)} chars)")
            return fixed
    except Exception as e:
        logger.warning(f"⚠️  Fix pass failed (non-fatal): {e}")
    return code


def _remove_self_assignments(code: str) -> str:
    """Remove lines of the form `X = X` that cause UnboundLocalError."""
    import re
    cleaned = re.sub(r'^\s*(\w+)\s*=\s*\1\s*(?:#.*)?$', '', code, flags=re.MULTILINE)
    if cleaned != code:
        # Collapse any blank lines left behind (max 1 consecutive blank)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        logger.info("🧹 Removed self-assignment(s) from fix pass output")
    return cleaned


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
        tts_block = """self.set_speech_service(AzureService(voice="VOICE_NAME", global_speed=1.0))
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

CHEMISTRY FORMULA NOTATION (MANDATORY — affects Manim rendering):
- In structured_solution and all formula strings: write chemical formulas with LaTeX subscript notation so they render correctly in MathTex.
  CORRECT: CH_3CH_2OH, C_5H_{12}O_5, H_2SO_4, CO_2, ZnCl_2, C_8H_{10}N_4O_2
  WRONG:   CH₃CH₂OH, C₅H₁₂O₅, H₂SO₄, CO₂, ZnCl₂, C₈H₁₀N₄O₂
- Unicode subscripts (₀₁₂₃₄₅₆₇₈₉) and superscripts CANNOT be compiled by LaTeX and will crash the video render.
- Molar mass formula: M = \\sum (n_i \\times M_i), units as \\text{g/mol}

CHEMISTRY NAMING RULE (apply only when subject = chemistry, MANDATORY):
- NEVER read chemical formulas letter-by-letter in voiceover
- ALWAYS convert formulas to proper chemical names in spoken text
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
EXPLANATION DEPTH — FIRST PRINCIPLES (MANDATORY)
────────────────────────────────────────────────────────────
- Always explain WHY, not just WHAT — trace every concept back to the underlying principle
- Lead with a concrete real-world example or analogy BEFORE introducing any formula
- Address the "but why does that work?" question a curious student would ask
- If grade/level is provided, calibrate vocabulary and assumed prior knowledge:
  - Grade 6–8: everyday analogies, no algebra required
  - Grade 9–10: algebra/geometry OK, link to classroom context
  - Grade 11–12: pre-calculus OK, connect to exam topics and deeper mechanism
  - University: assume prerequisites, go deeper on mechanism and derivation
- Keep narration energetic and pacy — no long pauses, no filler phrases like "So, as we can see..."

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
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)  # INSIDE block — no silence gap

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
    self.wait(max(0.1, tracker.duration - 0.9))
    self.play(FadeOut(sub), run_time=0.4)  # INSIDE the block — no silence gap between beats

SUBTITLE RULES:
- show_subtitle MUST be a class method, NEVER a nested function inside construct()
- Every voiceover block MUST have a matching subtitle
- Call as self.show_subtitle(...), NEVER as show_subtitle(self, ...)
- FadeOut(sub) MUST be INSIDE the voiceover block — the last two lines before the block ends
- NEVER call self.play(FadeOut(sub)) OUTSIDE the voiceover block — it creates dead silence
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
- Maximum 5 elements visible in FOCUSED scenes (single molecule explanation, single formula derivation)
- PANEL LAYOUTS are exempt: a persistent left panel + divider + item list + right calculation zone
  counts as ONE layout context — the list rows, panel background, and divider stay on screen the whole time.
  Only the CALCULATION AREA refreshes between items (FadeOut old calc group, FadeIn new one).
- Use FadeOut before adding new FOCUSED content if screen is full

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

CHEMISTRY FORMULA RULE — MANDATORY, RENDER-CRITICAL:
- NEVER put Unicode subscripts (₀₁₂₃₄₅₆₇₈₉) or superscripts inside MathTex or Tex strings. LaTeX CANNOT compile them; the render will crash with a LaTeX error.
  CORRECT in MathTex: r"CH_3CH_2OH", r"C_5H_{12}O_5", r"H_2SO_4", r"M = \sum n_i \cdot M_i"
  WRONG   in MathTex: "CH₃CH₂OH", "C₅H₁₂O₅", "H₂SO₄"
- In Text() mobjects, Unicode IS fine: Text("CH₃CH₂OH") renders correctly via Pango.
- If formula variables are passed to MathTex, make sure those variables contain LaTeX notation, not Unicode subscripts.
- NEVER put $ signs inside MathTex strings — MathTex wraps everything in $…$ automatically.
  CORRECT: MathTex(r"C_{2}H_{5}OH")   WRONG: MathTex(r"C$_2$H$_5$OH")

CHEMISTRY NAMING RULE (MANDATORY):
- NEVER read chemical formulas letter-by-letter in voiceover
- ALWAYS convert formulas to proper chemical names in spoken text

══════════════════════════════════════════════════════════════════
CHEMISTRY OVERVIEW VIDEO PATTERN (multi-compound / multi-step)
══════════════════════════════════════════════════════════════════

USE THIS PATTERN when the video covers MULTIPLE COMPOUNDS or MULTIPLE ITEMS
with the SAME calculation/analysis framework (e.g. molar mass, Ka, solubility, enthalpy).

LAYOUT — TWO-PANEL (16:9):
  LEFT PANEL  (centered at LEFT*3.2):  persistent item list — stays on screen the whole time
  DIVIDER LINE at x = -1.0
  RIGHT ZONE  (calc_base = RIGHT*2.5 + UP*0.8): sequential calculation steps per item

SETUP CODE SKELETON:
  # Dark card panel — professional depth
  left_panel = Rectangle(width=4.5, height=7.5,
      fill_color=ManimColor("#161B22"), fill_opacity=0.9,
      stroke_color=ManimColor("#30363D"), stroke_width=1.5).move_to(LEFT*3.2)
  divider = Line(LEFT*1.0+UP*3.5, LEFT*1.0+DOWN*3.5,
      stroke_color=ManimColor("#30363D"), stroke_width=1.5)

  # Item list — stacked rows inside left panel
  items = [("Name1", r"Formula_1"), ("Name2", r"Formula_2"), ...]  # LaTeX, NO $ signs
  rows = VGroup()
  for idx, (name, formula) in enumerate(items):
      name_t    = Text(name, font_size=18, color=WHITE)
      formula_t = MathTex(formula, font_size=18, color=YELLOW)
      row = VGroup(name_t, formula_t).arrange(RIGHT, buff=0.3)
      row.move_to(LEFT*3.2 + UP*(1.8 - idx*0.72))
      rows.add(row)

  # Optional: formula/title in right panel — must be ABOVE UP*1.5 to clear calc area
  right_title = Text("Calculation", font_size=20, color=WHITE).move_to(RIGHT*2.5 + UP*2.8)

  # Calc lines — base at UP*0.8, stacked DOWN in 0.55-unit steps
  calc_base = RIGHT*2.5 + UP*0.8
  # calc_line1 at calc_base+DOWN*0.0, calc_line2 at DOWN*0.55, calc_line3 at DOWN*1.10
  # result_value at DOWN*1.75 in GREEN BOLD

  # Pre-create one SurroundingRectangle per item (or reuse one with Transform)
  rects = [SurroundingRectangle(rows[i], color=YELLOW, buff=0.12, stroke_width=2) for i in range(len(items))]

ANIMATION PATTERN per item:
  # Reveal panel once at start
  self.play(FadeIn(left_panel), FadeIn(divider))
  self.play(AnimationGroup(*[FadeIn(row) for row in rows], lag_ratio=0.2))

  for i, (calc_group, rect) in enumerate(zip(calc_groups, rects)):
      # Highlight active row
      self.play(Create(rect))
      self.play(Indicate(rows[i], scale_factor=1.1, color=YELLOW))
      # Show calc lines one at a time
      self.play(Write(calc_line1[i]))
      self.play(Write(calc_line2[i]))
      self.play(Write(calc_line3[i]))
      self.play(FadeIn(result_value[i]), FadeIn(result_unit[i]))
      self.play(Flash(result_value[i], color=GREEN, flash_radius=0.5, num_lines=10))
      # Clean up calc area before next item
      self.play(FadeOut(calc_group), FadeOut(rect))

HOOK BEFORE PANEL:
  Always open with a question-mark or intriguing hook beat (1-2 beats) BEFORE revealing
  the panel. Show a relevant molecule or concept visual, then transition to the panel layout.

CLOSING SUMMARY SCREEN:
  After all items: FadeOut the panel layout, then show a clean summary card
  (RoundedRectangle with GOLD stroke, centered at ORIGIN) listing all items + results.
  summary_bg = RoundedRectangle(width=9.0, height=6.5, corner_radius=0.3,
      fill_color=ManimColor("#161B22"), fill_opacity=0.95, stroke_color=GOLD, stroke_width=2)

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
   X must account for ALL animations in the beat including the FadeOut(sub) at the end.
   Minimum X = 0.9 (0.5s show_subtitle FadeIn + 0.4s FadeOut). Add more for extra animations.

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
            self.wait(max(0.1, tracker.duration - 0.9))
            self.play(FadeOut(sub), run_time=0.4)  # INSIDE block — no silence gap
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

6. Colors
STANDARD PALETTE: WHITE, YELLOW, RED, BLUE, GREEN, ORANGE, PURPLE, PINK, GRAY, GREY, BLACK
EXTENDED CONSTANTS (all valid in Manim): DARK_BLUE, TEAL, GOLD, LIGHT_GRAY, RED_E, GREEN_E, BLUE_E, TEAL_E, GOLD_E, MAROON
DARK PANEL FILLS: use ManimColor("#0D1117") for scene background, ManimColor("#161B22") for card/panel fills,
  ManimColor("#30363D") for panel stroke — these dark tones create professional depth; avoid flat BLACK for backgrounds

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
CRITICAL: SCREEN MANAGEMENT (MANDATORY)
══════════════════════════════════════════════════════════════════

FOCUSED SCENES: FadeOut old content before showing new content at the same position.
Do not stack two competing elements at the same screen zone.

PANEL LAYOUTS (multi-item overview videos): The persistent panel, divider, and item list
STAY on screen throughout. Only the calculation/detail zone on the right refreshes between items.
This is intentional — the list gives viewers navigation context.

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

- Each voiceover block ≈ 20–35 seconds (hook + animations + wait)
- 90s  → 3 beats  |  2 min → 4–5 beats  |  3 min → 6–7 beats  |  4–6 min → 8–10 beats
- NEVER rush beats — fewer longer beats beat many rushed ones
- Every beat must have at least one clear visual movement or reveal
- Voiceover text per beat: 2–4 sentences, spoken naturally in 15–25 seconds

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

# ── Subject-specific prompt files ─────────────────────────────────────────────────────
_PROMPTS_DIR = Path(__file__).parent / "prompts"

_SUBJECT_PROMPT_FILES: dict = {
    "physics":     "physics_prompt.txt",
    "chemistry":   "chemistry_prompt.txt",
    "mathematics": "mathematics_prompt.txt",
    "economics":   "economics_prompt.txt",
}

_prompt_file_cache: dict = {}


def _load_prompt_file(filename: str) -> str:
    """Load a prompt file from the prompts/ directory. Cached after first read."""
    if filename in _prompt_file_cache:
        return _prompt_file_cache[filename]
    path = _PROMPTS_DIR / filename
    try:
        content = path.read_text(encoding="utf-8")
        _prompt_file_cache[filename] = content
        return content
    except FileNotFoundError:
        logger.warning(f"⚠️  Prompt file not found: {path} — falling back to inline prompt")
        return ""


def _build_system_prompt(subject: str, aspect_ratio: str, language: str) -> str:
    """
    Build the Manim system prompt for the given subject.

    Strategy:
      1. Load base_prompt.txt (shared rules for all subjects).
         Falls back to the hardcoded _ULTIMATE_SYSTEM_PROMPT_TEMPLATE if file missing.
      2. Append the subject-specific prompt file (physics/chemistry/mathematics/economics).
         Skipped silently if no file exists for the subject (e.g. biology, general).
      3. Apply {{TTS_IMPORT}} / {{TTS_SERVICE_BLOCK}} placeholders.
      4. Append RUNTIME CONFIGURATION block (aspect ratio + language).
    """
    # 1. Base prompt
    base = _load_prompt_file("base_prompt.txt")
    if not base:
        base = _ULTIMATE_SYSTEM_PROMPT_TEMPLATE  # inline fallback

    # 2. Subject-specific addendum
    subject_file = _SUBJECT_PROMPT_FILES.get(subject.lower(), "")
    subject_addendum = _load_prompt_file(subject_file) if subject_file else ""

    combined = base
    if subject_addendum:
        combined = combined + "\n\n" + subject_addendum
        logger.info(f"📄 Loaded subject prompt: {subject_file}")

    # 3. TTS placeholders
    combined = apply_tts_placeholders(combined)

    # 4. Runtime config
    manim_ver = settings.MANIM_VERSION
    runtime_config = f"""

══════════════════════════════════════════════════════════════════
RUNTIME CONFIGURATION
══════════════════════════════════════════════════════════════════

TARGET_ASPECT_RATIO: {aspect_ratio}
TARGET_LANGUAGE: {language}
MANIM_VERSION: {manim_ver} (Manim Community)

Adapt all positioning and font sizes according to TARGET_ASPECT_RATIO rules above.
Use TARGET_LANGUAGE for voiceover text and screen titles.

VERSION-SPECIFIC API NOTES FOR {manim_ver} (Manim Community):
REMOVED APIs (will cause NameError — do NOT use):
- ChangeDecimalValue → use decimal_obj.animate.set_value(new_val)
- ShowCreation       → use Create()
- CurvedDoubleArrow  → use DoubleArrow()
- ShowPassingFlashAround → use ShowPassingFlash()

CHANGED IN 0.18+:
- ManimColor is now the preferred color type: ManimColor("#rrggbb") for any hex color
- color= accepts ManimColor, named constants (WHITE/BLUE/etc.), or "#rrggbb" strings
- VGroup(*self.mobjects) is unreliable → use Group(*self.mobjects)
- FadeIn/FadeOut accept shift= kwarg: FadeIn(obj, shift=UP*0.3)
- Always use rate_func=smooth (not ease_in, ease_out, which don't exist)

DECIMALNUMBER BEST PRACTICE (0.19):
- In SETUP BLOCK: tracker = ValueTracker(initial_value)
                  display = always_redraw(lambda: DecimalNumber(tracker.get_value(), ...))
                  self.add(display)
- In animation beat: self.play(tracker.animate.set_value(new_val), run_time=1.5)
  (do NOT use ChangeDecimalValue — it was removed before 0.17)

VALID COLORS ONLY: WHITE, BLACK, RED, BLUE, GREEN, YELLOW, ORANGE, PURPLE, PINK,
GRAY, GREY, DARK_BLUE, DARK_BROWN, DARK_GRAY, LIGHT_GRAY, TEAL, GOLD, MAROON,
BLUE_A/B/C/D/E, GREEN_A/B/C/D/E, RED_A/B/C/D/E, GRAY_A/B/C/D/E,
TEAL_A/B/C/D/E, GOLD_A/B/C/D/E, MAROON_A/B/C/D/E, PURPLE_A/B/C,
or ManimColor("#rrggbb") for any custom color.
"""
    return combined + runtime_config


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
        # Title position
        (r'title\.move_to\(UP \* [6-9](?:\.[0-9]+)?\)', 'title.move_to(UP * 3.5)', "Adjusting title for landscape"),
        # Font sizes
        (r'font_size\s*=\s*20(?![0-9])', 'font_size=24', "Increasing small fonts"),
        (r'font_size\s*=\s*24(?![0-9])', 'font_size=28', "Increasing medium fonts"),
        (r'font_size\s*=\s*3[2-9](?![0-9])', 'font_size=28', "Adjusting large fonts for landscape"),
        # SMILES helper: move molecule from portrait positions to LEFT panel
        (r'create_molecule_from_smiles\(([^)]*?)position\s*=\s*ORIGIN(?=[,\)])',
         r'create_molecule_from_smiles(\1position=LEFT * 3.0',
         "Moving SMILES molecule from ORIGIN to LEFT panel"),
        (r'create_molecule_from_smiles\(([^)]*?)position\s*=\s*UP\s*\*\s*[0-9]+(?:\.[0-9]+)?(?=[,\)])',
         r'create_molecule_from_smiles(\1position=LEFT * 3.0',
         "Moving SMILES molecule from portrait position to LEFT panel"),
        # Manual hexagon molecules (benzene) placed at ORIGIN — move to LEFT panel
        (r'(hexagon|benzene_ring|ring_group|molecule_group)\.move_to\(ORIGIN\)',
         r'\1.move_to(LEFT * 3.0)',
         "Moving hexagon/molecule from ORIGIN to LEFT panel"),
        (r'(hexagon|benzene_ring|structural_svg|aspirin_svg|molecule)\.move_to\(ORIGIN\s*\+\s*(?:LEFT|RIGHT)\s*\*\s*[0-9.]+\)',
         r'\1.move_to(LEFT * 3.0)',
         "Correcting molecule position to LEFT panel"),
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
    # "atom" intentionally omitted — use draw_bohr_atom() helper instead
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
    # "nucleus" intentionally omitted — use draw_bohr_atom() helper instead
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
    "planet": "planet_orbit", "orbit": "planet_orbit",
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
        # Word-boundary match — plain substring match false-positives on short
        # keywords buried in longer words (e.g. "car" inside "carboxylic acid").
        if asset not in seen and re.search(rf"\b{re.escape(keyword)}\b", text_lower):
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
            text = _first_text(msg).strip()
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
    return _strip_svg_markdown(_first_text(msg))


def _svg_asset_url(r2_key: str) -> str:
    """
    Return the best permanent URL for an R2 SVG asset.
    Prefers the public R2_PUBLIC_URL (no expiry) over a 1-hour presigned URL.
    Presigned URLs expire before Cloud Run renders the video — public URLs don't.
    """
    if R2_PUBLIC_URL:
        return f"{R2_PUBLIC_URL.rstrip('/')}/{r2_key}"
    # Fallback: presigned URL (expires in 24 h — longer than default 1 h to
    # reduce chance of expiry, but still not ideal for slow render queues)
    return r2_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": r2_key},
        ExpiresIn=86400,
    )


def generate_svg_assets(svg_list: list) -> tuple[dict, dict]:
    """
    For each asset: check R2 cache, generate via Claude, upload.
    Returns ({name: url}, {name: svg_xml_string}).
    The svg_xml_string dict is used to embed SVGs inline in the generated code,
    eliminating the need for Cloud Run to download from R2 (avoids 403 on private buckets).
    """
    MAX_ASSETS = 5
    svg_urls: dict = {}
    svg_xml_map: dict = {}
    if r2_client is None:
        logger.warning("⚠️  R2 not configured — skipping SVG asset generation")
        return svg_urls, svg_xml_map

    for asset_name in svg_list[:MAX_ASSETS]:
        r2_key = f"svg_assets/{asset_name}.svg"
        if r2_object_exists(r2_key):
            logger.info(f"🖼️  SVG cache hit: {asset_name}")
            try:
                svg_urls[asset_name] = _svg_asset_url(r2_key)
                # Read content for inline injection (avoids public-URL 403 at render time)
                resp = r2_client.get_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
                svg_xml_map[asset_name] = resp["Body"].read().decode("utf-8")
            except Exception as e:
                logger.warning(f"⚠️  Could not read cached SVG '{asset_name}': {e}")
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
            svg_urls[asset_name] = _svg_asset_url(r2_key)
            svg_xml_map[asset_name] = svg_xml
            logger.info(f"✅ SVG uploaded: {r2_key}")
        except Exception as e:
            logger.error(f"❌ R2 upload failed for '{asset_name}': {e}")
    return svg_urls, svg_xml_map


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


# ── Bohr atom helper code — injected into chemistry videos at Cloud Run dispatch time ──
_ATOM_BOHR_CODE: str = '''
ATOM_CONFIGS = {
    "H":  ([1],             "#DDDDDD"),
    "He": ([2],             "#C8E8FF"),
    "Li": ([2, 1],          "#CC3333"),
    "Be": ([2, 2],          "#228844"),
    "B":  ([2, 3],          "#DD7700"),
    "C":  ([2, 4],          "#888888"),
    "N":  ([2, 5],          "#4477EE"),
    "O":  ([2, 6],          "#EE3333"),
    "F":  ([2, 7],          "#33BB77"),
    "Ne": ([2, 8],          "#99CCFF"),
    "Na": ([2, 8, 1],       "#FFCC22"),
    "Mg": ([2, 8, 2],       "#22AA55"),
    "Al": ([2, 8, 3],       "#AAAAAA"),
    "Si": ([2, 8, 4],       "#BBBBBB"),
    "P":  ([2, 8, 5],       "#FF7722"),
    "S":  ([2, 8, 6],       "#FFDD00"),
    "Cl": ([2, 8, 7],       "#44CC44"),
    "Ar": ([2, 8, 8],       "#AABBFF"),
    "K":  ([2, 8, 8, 1],    "#BB44AA"),
    "Ca": ([2, 8, 8, 2],    "#22AA44"),
}


def draw_bohr_atom(symbol, position=ORIGIN, scale=1.0, electron_color=YELLOW, shell_color=GRAY, shells=None, color=None):
    """Draw a Bohr-model atom; returns a VGroup (nucleus + shell rings + electron dots).
    shells: override electron counts per shell (e.g. [2,8] for Na+ ion). If None, uses ATOM_CONFIGS.
    color: alias for electron_color (backwards compat).
    """
    import math as _m
    if color is not None:
        electron_color = color
    cfg_shells, nuc_hex = ATOM_CONFIGS.get(symbol, ([1], "#888888"))
    if shells is None:
        shells = cfg_shells
    group = VGroup()

    nuc_r = 0.28 * scale
    nucleus  = Circle(radius=nuc_r, fill_color=ManimColor(nuc_hex), fill_opacity=1,
                      stroke_color=WHITE, stroke_width=1.5)
    sym_text = Text(symbol, font_size=int(16 * scale), color=WHITE)
    nuc_group = VGroup(nucleus, sym_text)
    nuc_group.move_to(position)
    group.add(nuc_group)

    base_radii = [0.62, 1.08, 1.54, 2.00]
    for i, count in enumerate(shells):
        r = base_radii[i] * scale
        ring = Circle(radius=r, stroke_color=shell_color, stroke_width=1.2,
                      fill_opacity=0, stroke_opacity=0.55).move_to(position)
        group.add(ring)
        for j in range(count):
            angle = (2 * _m.pi * j / count) - _m.pi / 2
            ex = position[0] + r * _m.cos(angle)
            ey = position[1] + r * _m.sin(angle)
            group.add(Dot(radius=0.072 * scale, color=electron_color).move_to([ex, ey, 0]))

    return group
'''


def _strip_llm_atom_definitions(code: str) -> str:
    """Remove any LLM-written draw_bohr_atom() / ATOM_CONFIGS definitions using AST."""
    import ast as _ast
    try:
        tree = _ast.parse(code)
    except SyntaxError:
        return code
    lines = code.splitlines(keepends=True)
    to_remove: set = set()
    for node in tree.body:
        if isinstance(node, _ast.FunctionDef) and node.name == 'draw_bohr_atom':
            for ln in range(node.lineno, node.end_lineno + 1):
                to_remove.add(ln)
        elif isinstance(node, _ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, _ast.Name) and tgt.id == 'ATOM_CONFIGS':
                    for ln in range(node.lineno, node.end_lineno + 1):
                        to_remove.add(ln)
    if not to_remove:
        return code
    result = ''.join(line for i, line in enumerate(lines, 1) if i not in to_remove)
    return re.sub(r'\n{3,}', '\n\n', result)


def inject_atom_helper(code: str, subject: str) -> str:
    """Strip any LLM-written draw_bohr_atom/ATOM_CONFIGS, then inject the canonical version."""
    if subject != "chemistry":
        return code
    if "draw_bohr_atom" not in code:
        return code
    # Always strip LLM's version(s) — they may have wrong signature or be copied from prompt
    code = _strip_llm_atom_definitions(code)
    match = re.search(r'^class\s+\w+', code, re.MULTILINE)
    if not match:
        return code
    insert_pos = match.start()
    return code[:insert_pos] + _ATOM_BOHR_CODE.strip() + "\n\n\n" + code[insert_pos:]


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
    "YELLOW_GREEN": "YELLOW", "CHARTREUSE": "GREEN", "AQUA": "TEAL",
    "LIGHT_BLUE": "BLUE_B", "DARK_GREEN": "GREEN_E", "DARK_RED": "RED_E",
    "LIGHT_GREEN": "GREEN_B", "LIGHT_YELLOW": "YELLOW", "LIGHT_PURPLE": "PURPLE_A",
}


def fix_manim_colors(code: str) -> str:
    """Replace color constants not defined in Manim with valid equivalents."""
    for bad, good in _INVALID_MANIM_COLORS.items():
        code = re.sub(rf'\b{bad}\b', good, code)
    return code


# Removed/renamed Manim APIs the LLM hallucinates from older training data.
# Each entry: regex pattern → replacement string (re.sub compatible).
_DEPRECATED_MANIM_APIS: list[tuple[str, str]] = [
    # ChangeDecimalValue was removed — use .animate.set_value()
    (r'\bChangeDecimalValue\s*\(\s*(\w+)\s*,\s*([^,)]+)\)',
     r'\1.animate.set_value(\2)'),
    # ShowCreation was renamed to Create in Manim Community
    (r'\bShowCreation\b', 'Create'),
    # CurvedDoubleArrow is not in Manim Community
    (r'\bCurvedDoubleArrow\b', 'DoubleArrow'),
    # Restore → deprecated, use Transform
    (r'\bRestore\b', 'FadeIn'),
    # ApplyWave not in Manim Community
    (r'\bApplyWave\b', 'Indicate'),
]


def fix_deprecated_manim_apis(code: str) -> str:
    """Replace removed or renamed Manim APIs with their current equivalents."""
    for pattern, replacement in _DEPRECATED_MANIM_APIS:
        new_code, count = re.subn(pattern, replacement, code)
        if count:
            logger.info(f"🔧 Replaced deprecated API ({pattern[:40]}…) × {count}")
        code = new_code
    return code


_LATEX_MOBJECT_RE = re.compile(r'\b(?:MathTex|Tex|SingleStringMathTex)\s*\(')
_WEIGHT_KWARG_RE  = re.compile(r',?\s*weight\s*=\s*[A-Za-z_][A-Za-z0-9_.]*')


def strip_invalid_tex_weight(code: str) -> str:
    """
    Local hotfix, not synced from AnimLearn: MathTex/Tex (LaTeX-rendered mobjects)
    don't accept a `weight=` kwarg in this Manim version — only Text/MarkupText do.
    The AI occasionally adds it anyway, crashing the render with
    "Mobject.__init__() got an unexpected keyword argument 'weight'" (seen on
    videos 30 and 31). Strip weight=... only from MathTex/Tex calls — paren-depth
    matched so it's safe with nested calls like ManimColor("#66BB6A") — leaving
    Text(...) calls (where weight is valid) untouched.
    """
    out, i, n = [], 0, len(code)
    while True:
        m = _LATEX_MOBJECT_RE.search(code, i)
        if not m:
            out.append(code[i:])
            break
        out.append(code[i:m.end()])
        depth, j = 1, m.end()
        while j < n and depth > 0:
            if code[j] == '(':
                depth += 1
            elif code[j] == ')':
                depth -= 1
            j += 1
        call_args = _WEIGHT_KWARG_RE.sub('', code[m.end():j - 1])
        out.append(call_args)
        out.append(')')
        i = j
    return ''.join(out)


_SUBSCRIPT_TO_LATEX = str.maketrans(
    '₀₁₂₃₄₅₆₇₈₉',
    # mapped to ASCII placeholder; we expand to _{N} with a second pass
    '0123456789',
)
_SUPERSCRIPT_TO_LATEX = str.maketrans(
    '⁰¹²³⁴⁵⁶⁷⁸⁹',
    '0123456789',
)

_SUBSCRIPT_CHARS    = set('₀₁₂₃₄₅₆₇₈₉')
_SUPERSCRIPT_CHARS  = set('⁰¹²³⁴⁵⁶⁷⁸⁹')
_SUB_MAP  = dict(zip('₀₁₂₃₄₅₆₇₈₉', [f'_{{{d}}}' for d in '0123456789']))
_SUP_MAP  = dict(zip('⁰¹²³⁴⁵⁶⁷⁸⁹', [f'^{{{d}}}' for d in '0123456789']))


def _unicode_to_latex_subscripts(s: str) -> str:
    """Replace Unicode sub/superscripts with LaTeX equivalents, grouping consecutive digits."""
    # e.g. CH₃CH₂OH → CH_{3}CH_{2}OH, CO₂ → CO_{2}, x² → x^{2}
    result = []
    i = 0
    while i < len(s):
        c = s[i]
        if c in _SUBSCRIPT_CHARS:
            digits = []
            while i < len(s) and s[i] in _SUBSCRIPT_CHARS:
                digits.append(_SUB_MAP[s[i]][2:-1])  # extract the digit
                i += 1
            result.append(f"_{{{''.join(digits)}}}")
        elif c in _SUPERSCRIPT_CHARS:
            digits = []
            while i < len(s) and s[i] in _SUPERSCRIPT_CHARS:
                digits.append(_SUP_MAP[s[i]][2:-1])
                i += 1
            result.append(f"^{{{''.join(digits)}}}")
        else:
            result.append(c)
            i += 1
    return ''.join(result)


def fix_unicode_in_mathtex(code: str) -> str:
    """
    Replace Unicode subscripts (₀₁₂₃₄₅₆₇₈₉) and superscripts (⁰¹²³⁴⁵⁶⁷⁸⁹)
    with LaTeX equivalents (_{N} / ^{N}) inside MathTex() and Tex() call
    boundaries. LaTeX cannot compile Unicode sub/superscripts and crashes with
    a 'latex error converting to dvi' — seen on video 51 (chemistry molar mass).
    Uses the same paren-depth walker as strip_invalid_tex_weight.
    """
    any_uni = _SUBSCRIPT_CHARS | _SUPERSCRIPT_CHARS
    if not any(c in code for c in any_uni):
        return code  # fast path — nothing to do

    out, i, n = [], 0, len(code)
    while True:
        m = _LATEX_MOBJECT_RE.search(code, i)
        if not m:
            out.append(code[i:])
            break
        out.append(code[i:m.end()])
        depth, j = 1, m.end()
        while j < n and depth > 0:
            if code[j] == '(':
                depth += 1
            elif code[j] == ')':
                depth -= 1
            j += 1
        call_body = code[m.end():j - 1]
        if any(c in call_body for c in any_uni):
            call_body = _unicode_to_latex_subscripts(call_body)
            logger.info("fix_unicode_in_mathtex: sanitised Unicode sub/superscripts in %s() call", m.group(0).strip('('))
        out.append(call_body)
        out.append(')')
        i = j
    return ''.join(out)


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


def _normalize_beats_indent(beats_code: str) -> str:
    """
    Ensure animation beats are indented at 8 spaces (inside construct()).
    Claude sometimes outputs at 4 spaces (function body) or 0 spaces (module level).
    Detects the base indent of the first non-empty, non-comment line and shifts
    everything so the base lands at 8 spaces.
    """
    lines = beats_code.split('\n')
    # Find base indent from the first real code line
    base = None
    for line in lines:
        stripped = line.lstrip()
        if stripped and not stripped.startswith('#'):
            base = len(line) - len(stripped)
            break
    if base is None or base == 8:
        return beats_code  # already correct or empty
    delta = 8 - base
    result = []
    for line in lines:
        if not line.strip():
            result.append('')
        else:
            cur = len(line) - len(line.lstrip())
            new_indent = max(0, cur + delta)
            result.append(' ' * new_indent + line.lstrip())
    logger.info(f"🔧 Beats indentation normalized: {base} → 8 spaces")
    return '\n'.join(result)


def _strip_critic_prose(text: str) -> str:
    """
    Remove leading prose lines from a critic response so only Python code remains.
    The critic sometimes opens with an em-dash explanation or a sentence before the code.
    Scans for the first line that looks like the start of a Python file.
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        s = line.strip()
        if (s.startswith('from ') or s.startswith('import ')
                or s.startswith('class ') or s.startswith('def ')
                or (s.startswith('#') and i < 5)):
            if i > 0:
                logger.info(f"🔧 Critic: stripped {i} leading prose line(s)")
                return '\n'.join(lines[i:])
            return text
    return text


def _fix_svg_urls_in_code(code: str, svg_urls: dict) -> str:
    """
    Replace any URL Claude wrote inside get_svg("name", "URL", ...) with the
    correct URL from svg_urls. Claude sometimes hallucinates URLs (e.g. constructs
    a public R2 URL without the svg_assets/ path prefix, or invents one entirely).
    This regex pass ensures the code always calls the real, correct URL.
    """
    if not svg_urls:
        return code
    for name, correct_url in svg_urls.items():
        # Match: get_svg("name", "ANY_URL"  or  get_svg('name', 'ANY_URL'
        # Captures the opening quote style so we can handle both.
        pattern = (
            r'(get_svg\s*\(\s*["\']'
            + re.escape(name)
            + r'["\'],\s*)["\'][^"\']*["\']'
        )
        replacement = r'\g<1>"' + correct_url + '"'
        new_code, n = re.subn(pattern, replacement, code)
        if n:
            logger.info(f"🔧 Fixed SVG URL for '{name}' ({n} occurrence(s))")
        code = new_code
    return code


def _assemble_two_pass_code(setup_code: str, beats_code: str) -> str:
    """Normalize beats indentation then splice them into the setup block at the sentinel."""
    beats_code = _normalize_beats_indent(beats_code)
    if _PHASE2_SENTINEL in setup_code:
        idx = setup_code.index(_PHASE2_SENTINEL) + len(_PHASE2_SENTINEL)
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
- Any `self.play()` calls — not even FadeOut, not even "to pre-hide" an object
- Any animation logic of any kind

⚠️ SILENT GLITCH TRAP — the most common setup block mistake:
  ❌ WRONG (causes silent flashes at video start):
      obj = Text("hello")
      self.play(FadeOut(obj))   ← DO NOT do this in setup
  ✅ CORRECT (object is invisible until a beat shows it):
      obj = Text("hello")       ← just define it, nothing else
  Objects defined in setup are NOT on screen until a beat calls self.play(FadeIn(obj)).
  Never call self.play() in setup to "hide" or "pre-position" anything.

STORYBOARD (read EVERY scene — define EVERY object mentioned):
{storyboard_text}

{svg_section}

ASPECT RATIO: {aspect_ratio}  |  LANGUAGE: {language}  |  DURATION: {duration}s  |  SUBJECT: {subject}

VERIFIED SOLUTION (formula values and variable names — use these exactly):
{verified_solution[:700]}

CODE LENGTH BUDGET: Target 150-250 lines total. Use short but descriptive variable names.
No in-code comments unless absolutely necessary for correctness.

Output ONLY valid Python code. No markdown fences. No explanation.
LAST LINE MUST BE EXACTLY (8 spaces indent):
        {_PHASE2_SENTINEL}
"""

    setup_code = _call_generation_pass(system_prompt, prompt, 32000, "setup block")
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
4. `            self.wait(max(0.1, tracker.duration - 0.9))`
5. `            self.play(FadeOut(sub), run_time=0.4)` ← INSIDE the block, last line

⚠️ FadeOut(sub) MUST be inside the `with` block. Placing it outside creates silence between beats.

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

CODE LENGTH BUDGET: 10-20 lines per beat. No in-code comments. Be concise.
Total beats output should be under 300 lines.

Output ONLY animation beats, indented 8 spaces.
Start directly with: `        with self.voiceover(`
No markdown fences. No imports. No class. No setup code.
"""

    beats_code = _call_generation_pass(system_prompt, prompt, 32000, "animation beats")
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
    svg_urls: dict = {}
    svg_xml_map: dict = {}
    if svg_list:
        logger.info(f"🖼️  SVG plan: {svg_list}")
        svg_urls, svg_xml_map = generate_svg_assets(svg_list)
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
            num_scenes = max(3, min(duration // 25, 10))
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
            max_tokens=8000,
            messages=[{"role": "user", "content": storyboard_prompt}]
        )
        storyboard_text = _first_text(storyboard_response).strip()
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
    code = fix_deprecated_manim_apis(code)
    code = ensure_numpy_import(code)
    code = strip_invalid_tex_weight(code)
    code = re.sub(r'VGroup\(\s*\*\s*self\.mobjects\s*\)', 'Group(*self.mobjects)', code)

    # Fix hallucinated / expired SVG URLs in get_svg() calls
    if svg_urls:
        code = _fix_svg_urls_in_code(code, svg_urls)

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
        code = re.sub(r"^import base64[^\n]*\n", "", code, flags=re.MULTILINE)

        # Build inline SVG data dict from xml map (avoids HTTP 403 on private R2 buckets)
        import base64 as _b64_module
        svg_data_entries = []
        for _name, _xml in svg_xml_map.items():
            _b64 = _b64_module.b64encode(_xml.encode("utf-8")).decode("ascii")
            svg_data_entries.append(f'    "{_name}": "{_b64}"')
        svg_data_block = "_SVG_DATA = {\n" + ",\n".join(svg_data_entries) + "\n}\n"

        svg_helper = (
            "import base64 as _b64_svg, os as _os\n\n"
            + svg_data_block + "\n"
            "def get_svg(name, url=None, height=0.8):\n"
            "    \"\"\"Write inline SVG to /tmp and return as a sized SVGMobject.\"\"\"\n"
            "    tmp = f\"/tmp/svg_{name}.svg\"\n"
            "    if not _os.path.exists(tmp):\n"
            "        if name in _SVG_DATA:\n"
            "            with open(tmp, 'wb') as _f:\n"
            "                _f.write(_b64_svg.b64decode(_SVG_DATA[name]))\n"
            "        elif url:\n"
            "            import urllib.request\n"
            "            urllib.request.urlretrieve(url, tmp)\n"
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
    # Static checklist goes in the system prompt (cached); only dynamic parts
    # (SVG list + code) go in the user message so the cache hit applies on
    # every call that shares the same checklist within the 5-min cache TTL.
    _CRITIC_SYSTEM = """You are a Manim animation quality critic. The user will give you Python code for a Manim animation. Review it and fix any issues from the checklist below.

ANIMATION QUALITY CHECKLIST — check each item:

1. OBJECT MOTION: Does the main object physically MOVE at least once?
   Fix: Add MoveAlongPath or .animate.move_to() for the main object

2. FORCE ARROWS:
   a) Native Manim Arrow() objects (created with Arrow(start, end, ...)): use GrowArrow() NOT Create()
      Fix: Replace Create(arrow) → GrowArrow(arrow) for native Arrow() objects
   b) SVGMobjects from get_svg(): use FadeIn() NOT GrowArrow()
      GrowArrow() on an SVGMobject CRASHES: "Cannot call Mobject.get_start for a Mobject with no points"
      Fix: If a variable assigned via `= get_svg(...)` is passed to GrowArrow(), replace with FadeIn(var, shift=RIGHT*0.2)

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

13. EQUATION/FORMULA OVERLAP (CRITICAL — applies to ALL subjects: math, physics, chemistry):
    Find every pair of MathTex/Tex/Text objects defined at the SAME screen position (same .move_to() coordinates).
    If object B is shown (FadeIn/Write/Create) AFTER object A at the same position,
    object A MUST be removed (FadeOut or ReplacementTransform) in the same or immediately preceding play() call.

    ❌ WRONG — stacking at same position:
       self.play(FadeIn(eq_step_1, ...))
       ...
       self.play(FadeIn(eq_step_2, ...))   # eq_step_1 still on screen → overlap

    ✅ CORRECT — fade out first:
       self.play(FadeOut(eq_step_1), FadeIn(eq_step_2, ...), ...)
    ✅ CORRECT — replacement transform:
       self.play(ReplacementTransform(eq_step_1, eq_step_2), ...)

    Fix: For every equation/formula shown after another at the same position, add FadeOut(prev_eq)
    to the same play() call as FadeIn(new_eq), or use ReplacementTransform(prev_eq, new_eq).
    This applies to: algebraic step equations (math), formula transitions and law text (physics),
    reaction equations and molecular formula updates (chemistry).

IMPORTANT: Only fix real problems. Do NOT restructure. Return ONLY the corrected Python code (no markdown fences).
If the code passes ALL checks above with no issues, output exactly: NO_CHANGES_NEEDED"""

    try:
        # Item 9 (SVG audit) is dynamic — put it in the user message with the code
        svg_audit_line = (
            f"9. SVG AUDIT: SVG assets available: {list(svg_urls.keys()) if svg_urls else 'none'}\n"
            "   If any named SVG object is drawn as a primitive shape, replace it with get_svg().\n\n"
        )
        critic_user = f"{svg_audit_line}CODE TO REVIEW:\n```python\n{code}\n```"

        critic_response = claude_with_retry(
            _claude_sync.messages.create,
            model=_CLAUDE_MODEL_FAST,
            max_tokens=64000,
            system=[{"type": "text", "text": _CRITIC_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": critic_user}]
        )
        critic_text = _first_text(critic_response).strip()
        if critic_text == "NO_CHANGES_NEEDED":
            logger.info("✅ Critic: code passed all checks — no changes needed (0 output tokens wasted)")
        else:
            if critic_text.startswith("```python"):
                critic_text = critic_text[len("```python"):].strip()
            if critic_text.startswith("```"):
                critic_text = critic_text[3:].strip()
            if critic_text.endswith("```"):
                critic_text = critic_text[:-3].strip()
            critic_text = _strip_critic_prose(critic_text)
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
    code = fix_deprecated_manim_apis(code)
    code = ensure_numpy_import(code)
    code = strip_invalid_tex_weight(code)

    # ─── AST undefined-name check + targeted fix pass ─────────────────────
    try:
        undefined = find_undefined_in_construct(code)
        if undefined:
            logger.warning(f"⚠️  Undefined names in construct(): {undefined}")
            code = fix_missing_definitions_pass(code, undefined)
            # Re-apply patches after fix
            code = re.sub(r'VGroup\(\s*\*\s*self\.mobjects\s*\)', 'Group(*self.mobjects)', code)
            code = fix_manim_colors(code)
            code = fix_deprecated_manim_apis(code)
            code = ensure_numpy_import(code)
            code = strip_invalid_tex_weight(code)
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
    code = inject_atom_helper(code, subject)

    # Syntax validation — try tab→space normalisation before giving up
    try:
        compile(code, "<generated>", "exec")
    except SyntaxError:
        normalised = code.expandtabs(4)
        try:
            compile(normalised, "<generated>", "exec")
            logger.warning("⚠️  Syntax fixed by tab→space normalisation")
            code = normalised
        except SyntaxError as syn_err:
            err = ValueError(f"Generated code has a syntax error (likely truncated): {syn_err}")
            err.partial_code = code  # type: ignore[attr-defined]
            raise err

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


# ─────────────────────────────────────────────────────────────────────────────────────
# FEEDBACK-DRIVEN IMPROVEMENT
# ─────────────────────────────────────────────────────────────────────────────────────

def _improve_manim_code_sync(
    original_code: str,
    feedback: str,
    subject: str,
    aspect_ratio: str,
    language: str,
) -> dict:
    """
    Take existing generated code + user feedback about layout/animation issues,
    return improved code that preserves all SVG base64 data exactly.
    """
    system_prompt = _build_system_prompt(subject, aspect_ratio, language)

    prompt = f"""You are given an existing Manim animation program and specific user feedback about layout or animation issues.

TASK: Fix ONLY the issues described in the feedback. Do not change the educational content, voiceover narration, or topic.

═══════════════════════════════════════════════════════════════
CRITICAL PRESERVATION RULES — VIOLATIONS WILL BREAK THE VIDEO
═══════════════════════════════════════════════════════════════
1. The _SVG_DATA dict contains base64-encoded SVG assets embedded in the code.
   Copy it CHARACTER-FOR-CHARACTER. Do not alter a single byte of any base64 string.
2. The get_svg() helper function must remain exactly as-is.
3. All voiceover text (strings inside self.voiceover(...)) must remain UNCHANGED.
4. The class name must remain unchanged.
5. Only fix: positions, sizes, colors, animation timing, panel placement,
   and other visual issues described in the feedback.

════════════════════════
USER FEEDBACK TO ADDRESS
════════════════════════
{feedback}

════════════════════════
ORIGINAL CODE
════════════════════════
```python
{original_code}
```

Return ONLY the improved Python code with no markdown fences."""

    message = claude_with_retry(
        _claude_sync.messages.create,
        model=_CLAUDE_MODEL_FAST,
        max_tokens=64000,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}]
    )

    improved = _first_text(message).strip()
    # Strip markdown fences if the model wrapped anyway
    improved = re.sub(r"^```[a-z]*\n?", "", improved, flags=re.IGNORECASE)
    improved = re.sub(r"\n?```$", "", improved).strip()

    _cu = getattr(message, "usage", None)
    if _cu:
        logger.info(
            f"[improve] write={getattr(_cu,'cache_creation_input_tokens',0)} "
            f"read={getattr(_cu,'cache_read_input_tokens',0)}"
        )

    return {"generated_code": improved}


async def improve_manim_code(
    original_code: str,
    feedback: str,
    subject: str,
    aspect_ratio: str,
    language: str,
) -> dict:
    """Async wrapper — runs the feedback-improvement pass in a thread."""
    return await asyncio.to_thread(
        _improve_manim_code_sync,
        original_code, feedback, subject, aspect_ratio, language,
    )


# ─────────────────────────────────────────────────────────────────────────────────────
# PHASE 2.5 — AUTO ERROR-FIX
# ─────────────────────────────────────────────────────────────────────────────────────

def _fix_manim_error_sync(
    original_code: str,
    error_message: str,
    subject: str,
    aspect_ratio: str,
    language: str,
) -> dict:
    """
    Phase 2.5: given Manim code that failed to render + the full error traceback,
    ask Claude to fix ONLY the code error while preserving all content, SVG assets,
    and voiceover text exactly. Cheaper and faster than a full Phase 1+2 re-run.
    """
    system_prompt = _build_system_prompt(subject, aspect_ratio, language)

    prompt = f"""You are given a Manim animation program that FAILED to render, and the full error traceback from the renderer.

TASK: Fix the Python/Manim error. Do NOT change the educational content, voiceover narration, topic, or SVG assets.

══════════════════════════════════════════
RENDERER ERROR (full traceback)
══════════════════════════════════════════
{error_message[:4000]}

══════════════════════════════════════════
FAILED CODE
══════════════════════════════════════════
```python
{original_code}
```

══════════════════════════════════════════
CRITICAL RULES
══════════════════════════════════════════
1. Fix ONLY what the error describes — do not restructure or rewrite the whole animation.
2. The _SVG_DATA dict base64 strings must be copied CHARACTER-FOR-CHARACTER, unchanged.
3. The get_svg() helper function must remain exactly as-is.
4. All self.voiceover(...) strings must remain UNCHANGED.
5. The scene class name must remain unchanged.
6. Common fixes to consider:
   - Wrong method name on a Manim object → look up correct API
   - Invalid LaTeX in MathTex(r"...") → escape or rewrite the expression
   - Off-screen coordinates → adjust to fit within [-7,7] x [-4,4]
   - Missing import → add at the top
   - Wrong argument type/count → correct the call signature
   - Undefined variable → define it or remove the reference

Return ONLY the corrected Python code with no markdown fences."""

    message = claude_with_retry(
        _claude_sync.messages.create,
        model=_CLAUDE_MODEL_FAST,
        max_tokens=64000,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )

    fixed = _first_text(message).strip()
    fixed = re.sub(r"^```[a-z]*\n?", "", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\n?```$", "", fixed).strip()

    _cu = getattr(message, "usage", None)
    if _cu:
        logger.info(
            f"[fix] write={getattr(_cu,'cache_creation_input_tokens',0)} "
            f"read={getattr(_cu,'cache_read_input_tokens',0)}"
        )

    return {"generated_code": fixed}


async def fix_manim_error(
    original_code: str,
    error_message: str,
    subject: str,
    aspect_ratio: str,
    language: str,
) -> dict:
    """Async wrapper for Phase 2.5 error-fix pass."""
    return await asyncio.to_thread(
        _fix_manim_error_sync,
        original_code, error_message, subject, aspect_ratio, language,
    )
