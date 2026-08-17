"""
AI model routing — central place for all model assignments and client creation.

Provider selection:
  - USE_AZURE_OPENAI=true → AsyncAzureOpenAI (EU, GDPR-compliant)
  - USE_AZURE_OPENAI=false (default) → AsyncOpenAI direct (US)

Change model assignments here without touching any other file.
"""
import json
import logging
from anthropic import AsyncAnthropic
from config import settings

logger = logging.getLogger(__name__)

# ── Vertex Gemini client factory ──────────────────────────────────────────────
# EU deployments: USE_VERTEX_GEMINI=true routes all Claude tasks to Gemini on
# Vertex AI (europe-west1). US deployments leave it false → Claude via Anthropic.

_GEMINI_PRO   = "gemini-2.5-pro"
_GEMINI_FLASH = "gemini-2.5-flash"
_GEMINI_LITE  = "gemini-2.5-flash-lite"

gemini_client = None
gemini_types  = None

def _make_vertex_gemini_client():
    global gemini_client, gemini_types
    if not settings.USE_VERTEX_GEMINI:
        logger.info("[ai_router] Claude provider: Anthropic (US)")
        return
    try:
        from google import genai as _genai
        from google.genai import types as _gtypes
        from google.oauth2 import service_account

        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            info  = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        else:
            creds = None  # falls back to ADC (local dev: gcloud auth application-default login)

        gemini_client = _genai.Client(
            vertexai=True,
            project=settings.VERTEX_PROJECT,
            location=settings.VERTEX_LOCATION,
            credentials=creds,
        )
        gemini_types = _gtypes
        logger.info(
            "[ai_router] Gemini provider: Vertex AI project=%s location=%s",
            settings.VERTEX_PROJECT, settings.VERTEX_LOCATION,
        )
    except Exception as exc:
        logger.error("[ai_router] Vertex Gemini init failed (%s) — falling back to Claude", exc)

_make_vertex_gemini_client()


async def ai_complete(
    system: str,
    messages: list[dict],
    max_tokens: int = 2048,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    """
    Provider-agnostic text completion.
    EU (USE_VERTEX_GEMINI=true)  → Gemini 2.5 Flash on Vertex europe-west1
    US (USE_VERTEX_GEMINI=false) → Claude Haiku on Anthropic
    messages: [{"role": "user"|"assistant", "content": "..."}]
    """
    if settings.USE_VERTEX_GEMINI and gemini_client:
        contents = []
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append(
                gemini_types.Content(
                    role=role,
                    parts=[gemini_types.Part(text=m["content"])],
                )
            )
        cfg = gemini_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            **({"response_mime_type": "application/json"} if json_mode else {}),
        )
        resp = await gemini_client.aio.models.generate_content(
            model=_GEMINI_FLASH,
            contents=contents,
            config=cfg,
        )
        return resp.text.strip()

    # Default: Claude Haiku
    resp = await claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return resp.content[0].text.strip()


# ── OpenAI client factory ─────────────────────────────────────────────────────

def _make_openai_client():
    if settings.USE_AZURE_OPENAI:
        from openai import AsyncAzureOpenAI
        logger.info(
            "[ai_router] OpenAI provider: Azure (%s)",
            settings.AZURE_OPENAI_ENDPOINT,
        )
        return AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    from openai import AsyncOpenAI
    logger.info("[ai_router] OpenAI provider: direct OpenAI API")
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

openai_client = _make_openai_client()
claude_client  = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# ── Azure deployment name mapping ─────────────────────────────────────────────
# Azure deployment names differ from OpenAI model names for audio models.
# gpt-4o and gpt-4o-mini deployment names match, so no mapping needed for those.
_AZURE_MODEL_MAP = {
    "whisper-1": "whisper",
    "tts-1":     "tts",
}

def resolve_model(model: str) -> str:
    """Return the correct model/deployment name for the active provider."""
    if settings.USE_AZURE_OPENAI:
        return _AZURE_MODEL_MAP.get(model, model)
    return model

# ── Model assignments ─────────────────────────────────────────────────────────
MODELS = {
    # Manim pipeline
    "manim_code_generation":     "claude-opus-4-7",
    "manim_critic_loop":         "claude-opus-4-7",
    "transcript_generation":     "claude-sonnet-4-6",
    "svg_generation":            "claude-sonnet-4-6",

    # Chat & teaching
    "chat_response":             "gpt-4o",
    "chat_response_vision":      "gpt-4o",
    "deep_explanation":          "claude-sonnet-4-6",

    # Quizzes
    "quiz_generation":           "gpt-4o",
    "quiz_difficulty_adapt":     "gpt-4o-mini",

    # Adaptive profile
    "profile_update":            "gpt-4o-mini",
    "prompt_modifier_rewrite":   "claude-haiku-4-5-20251001",

    # Metadata / utility
    "subject_detection":         "gpt-4o-mini",
    "title_generation":          "gpt-4o-mini",
    "suggestion_chips":          "gpt-4o-mini",
    "conversation_summary":      "gpt-4o-mini",
    "studyset_chat":             "gpt-4o",
}


def get_model(task: str) -> str:
    return resolve_model(MODELS.get(task, "gpt-4o"))


def is_claude_model(model: str) -> bool:
    return model.startswith("claude")


async def claude_complete(task: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """Call Claude for a given task."""
    model = MODELS.get(task, "claude-sonnet-4-6")
    resp = await claude_client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text


async def openai_complete(
    task: str,
    messages: list,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    response_format: dict | None = None,
) -> str:
    """Call OpenAI (or Azure OpenAI) for a given task."""
    model = get_model(task)
    kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
    if response_format:
        kwargs["response_format"] = response_format
    resp = await openai_client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content
