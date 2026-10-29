from story_stage.asset_library import DEFAULT_ACTION, DEFAULT_BACKGROUND, DEFAULT_CHARACTER_TYPE, DEFAULT_MOOD
from story_stage.schema import SceneValidationError, validate_scene


def test_valid_scene_round_trips_with_no_warnings():
    data = {
        "background": "forest",
        "characters": [
            {"id": "dragon_1", "type": "dragon", "x": 150, "y": 400, "mood": "sad", "action": "idle", "dialogue": "hi"},
        ],
        "events": [],
    }
    scene, warnings = validate_scene(data)

    assert warnings == []
    assert scene.background == "forest"
    assert scene.characters[0].id == "dragon_1"
    assert scene.characters[0].type == "dragon"
    assert scene.characters[0].mood == "sad"


def test_unknown_background_is_clamped_with_a_warning():
    data = {"background": "spaceship", "characters": [], "events": []}

    scene, warnings = validate_scene(data)

    assert scene.background == DEFAULT_BACKGROUND
    assert any("background" in w for w in warnings)


def test_unknown_character_type_is_clamped_with_a_warning():
    """The real stress test the product owner wants to run: a child
    saying something not in the vocabulary ("a dragon that's also a
    robot") must never crash the demo."""
    data = {
        "background": "forest",
        "characters": [{"id": "x", "type": "robot_dragon", "x": 100, "y": 100}],
        "events": [],
    }

    scene, warnings = validate_scene(data)

    assert scene.characters[0].type == DEFAULT_CHARACTER_TYPE
    assert any("type" in w for w in warnings)


def test_unknown_mood_and_action_are_clamped_independently():
    data = {
        "background": "forest",
        "characters": [{"id": "x", "type": "cat", "x": 100, "y": 100, "mood": "furious", "action": "flying"}],
        "events": [],
    }

    scene, warnings = validate_scene(data)

    assert scene.characters[0].mood == DEFAULT_MOOD
    assert scene.characters[0].action == DEFAULT_ACTION
    assert len(warnings) == 2


def test_out_of_bounds_coordinates_are_clamped_to_the_canvas():
    data = {
        "background": "forest",
        "characters": [{"id": "x", "type": "cat", "x": 99999, "y": -500}],
        "events": [],
    }

    scene, warnings = validate_scene(data)

    assert 0 <= scene.characters[0].x <= 1280
    assert 0 <= scene.characters[0].y <= 720
    assert len(warnings) == 2


def test_non_numeric_coordinate_falls_back_to_the_canvas_center():
    data = {"background": "forest", "characters": [{"id": "x", "type": "cat", "x": "far away", "y": 100}], "events": []}

    scene, warnings = validate_scene(data)

    assert scene.characters[0].x == 640
    assert any("x" in w for w in warnings)


def test_event_referencing_an_unknown_character_is_dropped():
    data = {
        "background": "forest",
        "characters": [{"id": "dragon_1", "type": "dragon", "x": 100, "y": 100}],
        "events": [{"type": "move", "character_id": "ghost_character", "to_x": 500}],
    }

    scene, warnings = validate_scene(data)

    assert scene.events == []
    assert any("ghost_character" in w for w in warnings)


def test_event_with_an_invalid_type_is_dropped():
    data = {
        "background": "forest",
        "characters": [{"id": "x", "type": "cat", "x": 100, "y": 100}],
        "events": [{"type": "teleport", "character_id": "x"}],
    }

    scene, warnings = validate_scene(data)

    assert scene.events == []
    assert any("teleport" in w for w in warnings)


def test_a_valid_move_event_survives_untouched():
    data = {
        "background": "forest",
        "characters": [{"id": "x", "type": "cat", "x": 100, "y": 100}],
        "events": [{"type": "move", "character_id": "x", "to_x": 500, "duration": 2.0}],
    }

    scene, warnings = validate_scene(data)

    assert warnings == []
    assert scene.events[0].type == "move"
    assert scene.events[0].to_x == 500
    assert scene.events[0].duration == 2.0


def test_non_dict_input_raises_scene_validation_error():
    import pytest

    with pytest.raises(SceneValidationError):
        validate_scene(["not", "a", "scene"])


def test_missing_character_id_raises_scene_validation_error():
    import pytest

    with pytest.raises(SceneValidationError):
        validate_scene({"background": "forest", "characters": [{"type": "cat", "x": 1, "y": 1}], "events": []})
