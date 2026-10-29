"""The scene data contract, and the deterministic gate every LLM reply
has to pass through before it's ever used -- same "propose, then
verify" principle as any other LLM output in this household's other
projects: the model's own JSON is a proposal, never trusted raw. Every
enum field gets clamped to a safe default (with a returned warning) if
the model violates its own instructions rather than ever letting an
unknown value reach the renderer, which has no idea what to do with
one.
"""
from dataclasses import dataclass, field

from .asset_library import (
    ACTIONS,
    BACKGROUNDS,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    CHARACTER_TYPES,
    DEFAULT_ACTION,
    DEFAULT_BACKGROUND,
    DEFAULT_CHARACTER_TYPE,
    DEFAULT_MOOD,
    EVENT_TYPES,
    MOODS,
)


@dataclass
class Character:
    id: str
    type: str
    x: float
    y: float
    mood: str = DEFAULT_MOOD
    action: str = DEFAULT_ACTION
    dialogue: str = ""


@dataclass
class Event:
    type: str
    character_id: str
    to_x: float | None = None
    duration: float = 1.0
    line: str = ""


@dataclass
class Scene:
    background: str
    characters: list[Character] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


class SceneValidationError(Exception):
    """Raised only when the input isn't even shaped like a scene at
    all (not a dict, "characters" isn't a list, etc.) -- the kind of
    malformed reply a retry should react to. A value that IS shaped
    right but violates an enum/range is NOT an error -- see
    validate_scene()'s own docstring for why those are clamped
    instead."""


def _clamp_enum(value: object, allowed: tuple[str, ...], default: str, warnings: list[str], field_name: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    warnings.append(f'{field_name}={value!r} is not one of {allowed} -- clamped to {default!r}')
    return default


def _clamp_coordinate(value: object, maximum: int, default: float, warnings: list[str], field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        warnings.append(f"{field_name}={value!r} isn't a number -- clamped to {default}")
        return default
    clamped = max(0.0, min(float(maximum), number))
    if clamped != number:
        warnings.append(f"{field_name}={number} is out of bounds -- clamped to {clamped}")
    return clamped


def validate_scene(data: object) -> tuple[Scene, list[str]]:
    """Validates and clamps a raw, parsed-JSON scene into a `Scene`.

    Deliberately lenient on enum/range violations -- clamps to a safe
    default and records a warning, rather than raising. The prompt
    already tells the model to "pick the closest available option,
    never invent new values" for exactly this case; a model that
    ignores that instruction anyway (the real stress test the product
    owner wants to run) shouldn't crash the demo -- it should degrade
    to a visibly imperfect but still-running scene, with the warning
    logged so the mismatch is visible without being fatal.

    Raises SceneValidationError only when the reply isn't even
    shaped like a scene (missing/wrong-typed required keys) -- that's
    a malformed reply worth retrying the LLM call over, not something
    clamping can meaningfully patch up.
    """
    if not isinstance(data, dict):
        raise SceneValidationError(f"scene must be a JSON object, got {type(data).__name__}")

    warnings: list[str] = []

    background = _clamp_enum(
        data.get("background"), BACKGROUNDS, DEFAULT_BACKGROUND, warnings, "background"
    )

    raw_characters = data.get("characters", [])
    if not isinstance(raw_characters, list):
        raise SceneValidationError("scene['characters'] must be a list")

    characters: list[Character] = []
    known_ids: set[str] = set()
    for i, raw in enumerate(raw_characters):
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
            raise SceneValidationError(f"characters[{i}] is missing a valid 'id'")
        char_id = raw["id"]
        characters.append(
            Character(
                id=char_id,
                type=_clamp_enum(
                    raw.get("type"), CHARACTER_TYPES, DEFAULT_CHARACTER_TYPE, warnings,
                    f"characters[{i}].type",
                ),
                x=_clamp_coordinate(
                    raw.get("x", CANVAS_WIDTH / 2), CANVAS_WIDTH, CANVAS_WIDTH / 2, warnings,
                    f"characters[{i}].x",
                ),
                y=_clamp_coordinate(
                    raw.get("y", CANVAS_HEIGHT / 2), CANVAS_HEIGHT, CANVAS_HEIGHT / 2, warnings,
                    f"characters[{i}].y",
                ),
                mood=_clamp_enum(
                    raw.get("mood", DEFAULT_MOOD), MOODS, DEFAULT_MOOD, warnings,
                    f"characters[{i}].mood",
                ),
                action=_clamp_enum(
                    raw.get("action", DEFAULT_ACTION), ACTIONS, DEFAULT_ACTION, warnings,
                    f"characters[{i}].action",
                ),
                dialogue=raw.get("dialogue", "") if isinstance(raw.get("dialogue", ""), str) else "",
            )
        )
        known_ids.add(char_id)

    raw_events = data.get("events", [])
    if not isinstance(raw_events, list):
        raise SceneValidationError("scene['events'] must be a list")

    events: list[Event] = []
    for i, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            warnings.append(f"events[{i}] isn't an object -- dropped")
            continue
        character_id = raw.get("character_id")
        if character_id not in known_ids:
            # Decision: a dangling reference (the model mentioning a
            # character it never declared) is dropped, not clamped --
            # there's no sane character to clamp it TO.
            warnings.append(
                f"events[{i}].character_id={character_id!r} doesn't match any declared "
                "character -- dropped"
            )
            continue
        event_type = raw.get("type")
        if event_type not in EVENT_TYPES:
            warnings.append(f"events[{i}].type={event_type!r} is not one of {EVENT_TYPES} -- dropped")
            continue
        to_x = raw.get("to_x")
        events.append(
            Event(
                type=event_type,
                character_id=character_id,
                to_x=_clamp_coordinate(to_x, CANVAS_WIDTH, 0.0, warnings, f"events[{i}].to_x")
                if to_x is not None else None,
                duration=float(raw["duration"]) if isinstance(raw.get("duration"), (int, float)) else 1.0,
                line=raw.get("line", "") if isinstance(raw.get("line", ""), str) else "",
            )
        )

    return Scene(background=background, characters=characters, events=events), warnings
