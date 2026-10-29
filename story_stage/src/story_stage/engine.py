"""Holds the current Scene and animates its one-shot `events` over
real wall-clock time -- the renderer just asks it "where is this
character right now" every frame; it never has to know about move
durations, speech timers, or jump arcs itself.

A fresh Scene from the LLM replaces the held one, but its own
`events` are consumed as animation instructions against the NEW
scene's already-placed characters (e.g. a "move" event's `to_x` is
where a character ends up; its *starting* x is wherever this new
scene already placed it, so a move visibly animates from the
character's last known position rather than teleporting -- the LLM
is told to keep a character's prior position as its "x" when the
narration doesn't mention moving it; see llm.py's PRIOR SCENE
instruction).
"""
import math
import time
from dataclasses import dataclass

from .schema import Character, Scene

_SPEECH_SECONDS = 3.5
_JUMP_SECONDS = 0.6
_JUMP_HEIGHT = 80.0


@dataclass
class _ActiveMove:
    character_id: str
    start_x: float
    to_x: float
    start_time: float
    duration: float


class SceneEngine:
    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self.scene: Scene | None = None
        self._active_moves: list[_ActiveMove] = []
        self._speech_until: dict[str, tuple[str, float]] = {}
        self._jump_started_at: dict[str, float] = {}

    def apply_scene(self, new_scene: Scene) -> None:
        """Adopts `new_scene` as the current scene and starts
        animating whichever of its events apply. Any animation left
        over from the previous scene is dropped -- a brand new scene
        (even one that's mostly the same characters) starts its own
        animations fresh rather than trying to reconcile two different
        events lists."""
        self.scene = new_scene
        self._active_moves.clear()
        self._speech_until.clear()
        self._jump_started_at.clear()
        now = self._clock()
        for event in new_scene.events:
            character = self._find(event.character_id)
            if character is None:
                continue
            if event.type == "move" and event.to_x is not None:
                self._active_moves.append(
                    _ActiveMove(event.character_id, character.x, event.to_x, now, max(event.duration, 0.01))
                )
            elif event.type == "speak":
                line = event.line or character.dialogue
                if line:
                    self._speech_until[event.character_id] = (line, now + _SPEECH_SECONDS)
            elif event.type == "jump":
                self._jump_started_at[event.character_id] = now

    def tick(self) -> None:
        """Advances every in-flight animation by however much real
        time has passed since the last tick. Call this once per
        rendered frame."""
        if self.scene is None:
            return
        now = self._clock()

        for move in list(self._active_moves):
            character = self._find(move.character_id)
            progress = min(1.0, (now - move.start_time) / move.duration)
            if character is not None:
                character.x = move.start_x + (move.to_x - move.start_x) * progress
            if progress >= 1.0:
                self._active_moves.remove(move)

        for character_id, (_line, expires_at) in list(self._speech_until.items()):
            if now >= expires_at:
                del self._speech_until[character_id]

        for character_id, started_at in list(self._jump_started_at.items()):
            if now - started_at >= _JUMP_SECONDS:
                del self._jump_started_at[character_id]

    def jump_offset(self, character_id: str) -> float:
        """A vertical offset (negative = up) for a character currently
        mid-jump, 0.0 otherwise -- one sine arc over _JUMP_SECONDS."""
        started_at = self._jump_started_at.get(character_id)
        if started_at is None:
            return 0.0
        progress = min(1.0, (self._clock() - started_at) / _JUMP_SECONDS)
        return -_JUMP_HEIGHT * math.sin(progress * math.pi)

    def speech_for(self, character_id: str) -> str | None:
        entry = self._speech_until.get(character_id)
        return entry[0] if entry else None

    def _find(self, character_id: str) -> Character | None:
        if self.scene is None:
            return None
        for character in self.scene.characters:
            if character.id == character_id:
                return character
        return None
