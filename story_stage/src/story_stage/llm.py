"""Turns one line of (messy, kid-style) narration into a validated
`Scene` -- the riskiest piece of this whole idea, per the brainstorm
this project exists to test: does an LLM reliably stay inside a fixed
sprite vocabulary when a child says something the vocabulary doesn't
cover ("a dragon that's also a robot")?

Only this module talks to the Anthropic API; schema.py's
validate_scene() is what actually decides whether a reply is usable --
this module's own retry is purely about malformed JSON (a reply that
isn't even parseable), never about re-litigating an enum choice
clamping already handles safely.
"""
import json
import os

from .asset_library import ACTIONS, BACKGROUNDS, CANVAS_HEIGHT, CANVAS_WIDTH, CHARACTER_TYPES, MOODS
from .schema import Scene, SceneValidationError, validate_scene

DEFAULT_MODEL = os.environ.get("STORY_STAGE_MODEL", "claude-sonnet-5-5")
_MAX_ATTEMPTS = 2  # one real try, one retry if the reply wasn't even valid JSON/shape


class SceneGenerationError(Exception):
    """Every attempt produced a reply that wasn't even shaped like a
    scene -- a real LLM/API problem (not a clamped-enum situation,
    which never raises)."""


def build_system_prompt() -> str:
    return (
        "You convert a child's spoken story narration into a strict JSON scene "
        "description for a 2D game renderer.\n\n"
        "Rules:\n"
        "- Output ONLY valid JSON, no prose, no markdown fences.\n"
        f"- \"type\" for each character MUST be one of: {list(CHARACTER_TYPES)}\n"
        f"- \"action\" MUST be one of: {list(ACTIONS)}\n"
        f"- \"mood\" MUST be one of: {list(MOODS)}\n"
        f"- \"background\" MUST be one of: {list(BACKGROUNDS)}\n"
        "- If the narration mentions something not in these lists, pick the closest "
        "available option. Never invent new values.\n"
        f"- x/y are screen coordinates on a {CANVAS_WIDTH}x{CANVAS_HEIGHT} canvas; "
        "characters should be spaced out, not overlapping.\n"
        "- Keep it simple: 1-3 characters per scene, 1-4 events.\n"
        "- If a PRIOR SCENE is given, UPDATE it: keep characters the narration doesn't "
        "mention, move/add/change only what the new narration actually describes. Only "
        "start a fresh scene with no prior one if none is given.\n\n"
        "Schema:\n"
        "{\n"
        '  "background": "<enum>",\n'
        '  "characters": [{"id": str, "type": "<enum>", "x": int, "y": int, '
        '"mood": "<enum>", "action": "<enum>", "dialogue": str}],\n'
        '  "events": [{"type": "move"|"speak"|"jump", "character_id": str, '
        '"to_x": int, "duration": float, "line": str}]\n'
        "}"
    )


def _scene_to_json(scene: Scene) -> str:
    return json.dumps(
        {
            "background": scene.background,
            "characters": [
                {
                    "id": c.id, "type": c.type, "x": c.x, "y": c.y,
                    "mood": c.mood, "action": c.action, "dialogue": c.dialogue,
                }
                for c in scene.characters
            ],
            "events": [],  # events are one-shot instructions, not part of persisted state
        }
    )


def _strip_markdown_fence(text: str) -> str:
    """Defensive only -- the prompt already says never to use fences,
    but a model ignoring that instruction shouldn't need a whole
    retry round trip over something this cheap to just strip."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: -3]
    return text.strip()


def narration_to_scene(
    client, narration: str, prior_scene: Scene | None = None, model: str = DEFAULT_MODEL,
) -> tuple[Scene, list[str]]:
    """Returns (scene, warnings). Raises SceneGenerationError if every
    attempt's reply wasn't even shaped like a scene."""
    system_prompt = build_system_prompt()
    user_content = narration
    if prior_scene is not None:
        user_content = f"PRIOR SCENE:\n{_scene_to_json(prior_scene)}\n\nNEW NARRATION:\n{narration}"

    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        messages = [{"role": "user", "content": user_content}]
        if attempt > 1 and last_error is not None:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Your last reply couldn't be parsed as the required JSON "
                        f"({last_error}). Reply again with ONLY the corrected JSON."
                    ),
                }
            )
        response = client.messages.create(
            model=model, max_tokens=1000, system=system_prompt, messages=messages,
        )
        text = _strip_markdown_fence(response.content[0].text)
        try:
            data = json.loads(text)
            return validate_scene(data)
        except (json.JSONDecodeError, SceneValidationError) as exc:
            last_error = exc
            continue

    raise SceneGenerationError(f"no valid scene after {_MAX_ATTEMPTS} attempts: {last_error}")
