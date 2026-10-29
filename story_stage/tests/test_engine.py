from story_stage.engine import SceneEngine
from story_stage.schema import Character, Event, Scene


class _FakeClock:
    """Deterministic stand-in for time.monotonic() -- SceneEngine
    takes a `clock` callable so tests control "now" exactly instead
    of racing real wall-clock time."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_move_event_animates_linearly_over_its_duration():
    clock = _FakeClock()
    engine = SceneEngine(clock=clock)
    scene = Scene(
        background="forest",
        characters=[Character(id="x", type="cat", x=0.0, y=100.0)],
        events=[Event(type="move", character_id="x", to_x=100.0, duration=2.0)],
    )

    engine.apply_scene(scene)
    assert engine.scene.characters[0].x == 0.0

    clock.advance(1.0)
    engine.tick()
    assert engine.scene.characters[0].x == 50.0

    clock.advance(1.0)
    engine.tick()
    assert engine.scene.characters[0].x == 100.0


def test_move_event_stops_exactly_at_to_x_even_if_more_time_passes():
    clock = _FakeClock()
    engine = SceneEngine(clock=clock)
    scene = Scene(
        background="forest",
        characters=[Character(id="x", type="cat", x=0.0, y=0.0)],
        events=[Event(type="move", character_id="x", to_x=100.0, duration=1.0)],
    )
    engine.apply_scene(scene)

    clock.advance(10.0)
    engine.tick()

    assert engine.scene.characters[0].x == 100.0


def test_speech_expires_after_a_few_seconds():
    clock = _FakeClock()
    engine = SceneEngine(clock=clock)
    scene = Scene(
        background="forest",
        characters=[Character(id="x", type="cat", x=0.0, y=0.0)],
        events=[Event(type="speak", character_id="x", line="Hello!")],
    )
    engine.apply_scene(scene)

    assert engine.speech_for("x") == "Hello!"

    clock.advance(10.0)
    engine.tick()

    assert engine.speech_for("x") is None


def test_speak_event_falls_back_to_the_characters_own_dialogue_when_no_line_is_given():
    clock = _FakeClock()
    engine = SceneEngine(clock=clock)
    scene = Scene(
        background="forest",
        characters=[Character(id="x", type="cat", x=0.0, y=0.0, dialogue="Meow!")],
        events=[Event(type="speak", character_id="x")],
    )
    engine.apply_scene(scene)

    assert engine.speech_for("x") == "Meow!"


def test_jump_offset_rises_then_returns_to_zero():
    clock = _FakeClock()
    engine = SceneEngine(clock=clock)
    scene = Scene(
        background="forest",
        characters=[Character(id="x", type="cat", x=0.0, y=0.0)],
        events=[Event(type="jump", character_id="x")],
    )
    engine.apply_scene(scene)

    assert engine.jump_offset("x") == 0.0  # just started, sin(0) == 0

    clock.advance(0.3)  # halfway through the 0.6s jump -- peak height
    assert engine.jump_offset("x") < -70.0

    clock.advance(1.0)
    engine.tick()
    assert engine.jump_offset("x") == 0.0


def test_a_new_scene_drops_leftover_animation_from_the_previous_one():
    clock = _FakeClock()
    engine = SceneEngine(clock=clock)
    first = Scene(
        background="forest",
        characters=[Character(id="x", type="cat", x=0.0, y=0.0)],
        events=[Event(type="move", character_id="x", to_x=1000.0, duration=10.0)],
    )
    engine.apply_scene(first)
    clock.advance(1.0)
    engine.tick()

    second = Scene(background="forest", characters=[Character(id="x", type="cat", x=5.0, y=5.0)], events=[])
    engine.apply_scene(second)
    clock.advance(1.0)
    engine.tick()

    # The old move event must not keep nudging "x" toward 1000 after a
    # brand new scene (with no move event of its own) was applied.
    assert engine.scene.characters[0].x == 5.0


def test_event_for_a_character_not_in_the_new_scene_is_ignored():
    clock = _FakeClock()
    engine = SceneEngine(clock=clock)
    scene = Scene(
        background="forest",
        characters=[Character(id="x", type="cat", x=0.0, y=0.0)],
        events=[Event(type="move", character_id="ghost", to_x=500.0, duration=1.0)],
    )

    engine.apply_scene(scene)  # must not raise
    engine.tick()

    assert engine.scene.characters[0].x == 0.0
