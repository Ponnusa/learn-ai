"""
AI model routing — central place for all model assignments and client creation.

Provider selection is automatic:
  - AZURE_OPENAI_ENDPOINT set → AsyncAzureOpenAI (EU, GDPR-compliant)
  - AZURE_OPENAI_ENDPOINT empty → AsyncOpenAI direct (US)

Change model assignments here without touching any other file.
"""
from anthropic import AsyncAnthropic
from config import settings

# ── OpenAI client factory ─────────────────────────────────────────────────────

def _make_openai_client():
    if settings.AZURE_OPENAI_ENDPOINT:
        from openai import AsyncAzureOpenAI
        return AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    from openai import AsyncOpenAI
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
    if settings.AZURE_OPENAI_ENDPOINT:
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
