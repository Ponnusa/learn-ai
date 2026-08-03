"""
AI model routing — same dual-AI pattern as AnimLearn.
Each task is assigned the best model. Change assignments here without
touching any other file.

Set USE_AZURE_OPENAI=true in env to route all OpenAI calls through
Azure OpenAI (Sweden Central) for EU data residency.
"""
from openai import AsyncOpenAI, AsyncAzureOpenAI
from anthropic import AsyncAnthropic
from config import settings

# ── OpenAI client — Azure or direct based on env flag ────────────────────────
if settings.USE_AZURE_OPENAI:
    openai_client = AsyncAzureOpenAI(
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )
else:
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

claude_client  = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# Azure doesn't have gpt-4o-mini (deprecated) — map to gpt-4o
_AZURE_MODEL_MAP = {
    "gpt-4o-mini": "gpt-4o",
    "tts-1":       "tts",
    "whisper-1":   "whisper",
}

# ── Model assignments ─────────────────────────────────────────────────────────
# Heavy reasoning / code generation → Claude (best for Manim code)
# Explanation / teaching / vision  → GPT-4o  (AnimLearn standard)
# Lightweight metadata tasks       → GPT-4o-mini / Claude Haiku

MODELS = {
    # Manim pipeline (copied verbatim from AnimLearn)
    "manim_code_generation":     "claude-opus-4-7",
    "manim_critic_loop":         "claude-opus-4-7",
    "transcript_generation":     "claude-sonnet-4-6",
    "svg_generation":            "claude-sonnet-4-6",

    # Chat & teaching
    "chat_response":             "gpt-4o",
    "chat_response_vision":      "gpt-4o",          # image + text
    "deep_explanation":          "claude-sonnet-4-6",

    # Quizzes
    "quiz_generation":           "gpt-4o",           # AnimLearn standard
    "quiz_difficulty_adapt":     "gpt-4o-mini",

    # Adaptive profile
    "profile_update":            "gpt-4o-mini",
    "prompt_modifier_rewrite":   "claude-haiku-4-5-20251001",

    # Metadata / utility
    "subject_detection":         "gpt-4o-mini",
    "title_generation":          "gpt-4o-mini",
    "suggestion_chips":          "gpt-4o-mini",
    "conversation_summary":      "gpt-4o-mini",   # rolling summary + topic extraction
    "studyset_chat":             "gpt-4o",        # grounded PDF chat — needs reasoning quality

    # Audio
    "whisper":                   "whisper-1",     # Azure deployment name: "whisper"
    "tts":                       "tts-1",         # Azure deployment name: "tts"
}


def get_model(task: str) -> str:
    model = MODELS.get(task, "gpt-4o")
    if settings.USE_AZURE_OPENAI:
        model = _AZURE_MODEL_MAP.get(model, model)
    return model


def is_claude_model(model: str) -> bool:
    return model.startswith("claude")


async def claude_complete(task: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """Call Claude for a given task."""
    model = get_model(task)
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
    """Call OpenAI for a given task."""
    model = get_model(task)
    kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
    if response_format:
        kwargs["response_format"] = response_format
    resp = await openai_client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content
