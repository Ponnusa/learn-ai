"""AI-generated contextual follow-up suggestion chips."""
import json
from services.ai_router import openai_client, get_model
from services.prompt_builder import _LANGUAGE_NAMES


async def generate_chips(reply: str, language: str = "en") -> list[str]:
    """
    Generate 3 topic-specific follow-up suggestion chips from an AI reply.
    Mix of: deeper questions, real-world examples, common mistake checks.
    Each must be ≤9 words and specific to the content — not generic.
    Falls back to an empty list on any error.
    """
    try:
        resp = await openai_client.chat.completions.create(
            model=get_model("suggestion_chips"),
            messages=[{
                "role": "user",
                "content": (
                    "Generate exactly 3 short follow-up prompts a student would naturally say "
                    "after reading this explanation. Rules:\n"
                    "- Each prompt ≤9 words\n"
                    "- Be SPECIFIC: mention actual concepts, formulas, or terms from the text\n"
                    "- Mix: one deeper question, one example/application request, one common-mistake check\n"
                    "- Do NOT use generic phrases like 'explain more' or 'tell me more'\n"
                    f"- Language: {language}\n"
                    f"- {'Write ALL suggestions in ' + _LANGUAGE_NAMES[language] + '. Do not use English.' if language in _LANGUAGE_NAMES else 'Write suggestions in English.'}\n"
                    "Return JSON: {\"suggestions\": [\"...\", \"...\", \"...\"]}\n\n"
                    f"{reply[:700]}"
                ),
            }],
            max_tokens=150,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        chips = data.get("suggestions") or data.get("chips") or []
        return [c for c in chips if isinstance(c, str) and c.strip()][:3]
    except Exception:
        return []
