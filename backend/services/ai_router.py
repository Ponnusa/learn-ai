"""
AI model routing — same dual-AI pattern as AnimLearn.
Each task is assigned the best model. Change assignments here without
touching any other file.
"""
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from config import settings

openai_client  = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
claude_client  = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

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
}


def get_model(task: str) -> str:
    return MODELS.get(task, "gpt-4o")


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
