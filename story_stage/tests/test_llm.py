import json

import pytest

from story_stage.llm import SceneGenerationError, narration_to_scene
from story_stage.schema import Character, Scene


class _FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    """Replays `replies` in order, one per .create() call -- lets a
    test script "the model's first reply was malformed JSON, its
    retry was valid" without touching the real API."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._replies.pop(0))


class _FakeClient:
    def __init__(self, replies: list[str]) -> None:
        self.messages = _FakeMessages(replies)


_VALID_SCENE_JSON = json.dumps(
    {
        "background": "forest",
        "characters": [{"id": "dragon_1", "type": "dragon", "x": 150, "y": 400, "mood": "sad"}],
        "events": [],
    }
)


def test_narration_to_scene_parses_a_clean_reply():
    client = _FakeClient([_VALID_SCENE_JSON])

    scene, warnings = narration_to_scene(client, "there's a sad dragon")

    assert warnings == []
    assert scene.characters[0].type == "dragon"
    assert len(client.messages.calls) == 1


def test_narration_to_scene_strips_a_markdown_fence_the_model_added_anyway():
    fenced = f"```json\n{_VALID_SCENE_JSON}\n```"
    client = _FakeClient([fenced])

    scene, _warnings = narration_to_scene(client, "there's a sad dragon")

    assert scene.characters[0].type == "dragon"


def test_narration_to_scene_retries_once_on_malformed_json():
    client = _FakeClient(["this is not json at all", _VALID_SCENE_JSON])

    scene, _warnings = narration_to_scene(client, "there's a sad dragon")

    assert scene.characters[0].type == "dragon"
    assert len(client.messages.calls) == 2
    # The retry's own extra message should mention the parse failure
    # so the model has something concrete to react to.
    retry_messages = client.messages.calls[1]["messages"]
    assert "couldn't be parsed" in retry_messages[-1]["content"]


def test_narration_to_scene_raises_after_exhausting_retries_on_bad_json():
    client = _FakeClient(["still not json", "also not json"])

    with pytest.raises(SceneGenerationError):
        narration_to_scene(client, "there's a sad dragon")

    assert len(client.messages.calls) == 2


def test_narration_to_scene_includes_the_prior_scene_as_context():
    client = _FakeClient([_VALID_SCENE_JSON])
    prior = Scene(background="forest", characters=[Character(id="dragon_1", type="dragon", x=150, y=400)])

    narration_to_scene(client, "a princess walks up", prior_scene=prior)

    sent_content = client.messages.calls[0]["messages"][0]["content"]
    assert "PRIOR SCENE" in sent_content
    assert "dragon_1" in sent_content
    assert "a princess walks up" in sent_content


def test_narration_to_scene_clamps_an_unknown_enum_value_instead_of_raising():
    """The real stress test: a reply with an out-of-vocabulary value
    is still VALID JSON (just not a value this prototype knows about)
    -- that's validate_scene()'s clamping job, not a retry-worthy
    parse failure."""
    reply = json.dumps(
        {"background": "forest", "characters": [{"id": "x", "type": "robot_dragon", "x": 1, "y": 1}], "events": []}
    )
    client = _FakeClient([reply])

    scene, warnings = narration_to_scene(client, "a dragon that's also a robot")

    assert scene.characters[0].type != "robot_dragon"
    assert any("type" in w for w in warnings)
    assert len(client.messages.calls) == 1  # clamping never triggers a retry
