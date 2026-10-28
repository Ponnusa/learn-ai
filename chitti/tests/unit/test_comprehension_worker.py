"""Unit tests for companion_robot.parent_controls.comprehension_worker
(decision 0131) -- real ConversationService + repositories, a fake
LLM backend, no real network/API calls.
"""
from datetime import datetime, timezone

from companion_robot.conversation.service import ConversationService
from companion_robot.parent_controls.comprehension_worker import run_once
from companion_robot.parent_controls.profiles import ChildProfile, ChildProfileRepository
from companion_robot.parent_controls.reading_exercises import (
    ReadingExerciseRecord,
    ReadingExerciseRepository,
)
from companion_robot.storage.sqlite import connect
from companion_robot.voice.interfaces import LanguageModelBackend


class _FakeLLM(LanguageModelBackend):
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[list[dict], str]] = []

    async def generate_reply(self, messages, system_prompt):
        self.calls.append((messages, system_prompt))
        return self.reply, "fake-model"


def _make_repos():
    conn = connect(":memory:")
    return ReadingExerciseRepository(conn), ChildProfileRepository(conn)


def _exercise(id_: str, child_profile_id: str = "child-1", **overrides) -> ReadingExerciseRecord:
    defaults = dict(
        id=id_,
        child_profile_id=child_profile_id,
        title="Homework",
        content="The cat sat on the mat.",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return ReadingExerciseRecord(**defaults)


def _profile(profile_id: str, age: int = 7) -> ChildProfile:
    now = datetime.now(timezone.utc)
    return ChildProfile(id=profile_id, name="Kid", age=age, created_at=now, updated_at=now)


async def test_run_once_generates_questions_for_a_pending_exercise():
    exercises, profiles = _make_repos()
    profiles.create(_profile("child-1"))
    exercises.create(_exercise("e1"))
    llm = _FakeLLM("QUESTION: Where did the cat sit?\nQUESTION: What color was the cat?")
    conversation = ConversationService(llm)

    processed = await run_once(exercises, profiles, conversation)

    assert processed == 1
    saved = exercises.list_for_child("child-1")[0]
    assert saved.comprehension_status == "generated"
    assert saved.comprehension_questions == [
        "Where did the cat sit?", "What color was the cat?",
    ]


async def test_run_once_never_touches_an_already_generated_exercise():
    exercises, profiles = _make_repos()
    profiles.create(_profile("child-1"))
    exercises.create(_exercise("e1"))
    exercises.save_generated_questions("e1", ["Already here?"])
    llm = _FakeLLM("QUESTION: A brand new question?")
    conversation = ConversationService(llm)

    processed = await run_once(exercises, profiles, conversation)

    assert processed == 0
    assert llm.calls == []
    unchanged = exercises.list_for_child("child-1")[0]
    assert unchanged.comprehension_questions == ["Already here?"]


async def test_run_once_marks_failed_when_nothing_usable_comes_back():
    """Every candidate question got dropped by check_speech() (or the
    reply had none at all) -- marked "failed" so the exact same
    content isn't retried every single poll."""
    exercises, profiles = _make_repos()
    profiles.create(_profile("child-1"))
    exercises.create(_exercise("e1"))
    llm = _FakeLLM("no QUESTION: lines at all")
    conversation = ConversationService(llm)

    processed = await run_once(exercises, profiles, conversation)

    assert processed == 1
    failed = exercises.list_for_child("child-1")[0]
    assert failed.comprehension_status == "failed"
    assert exercises.list_awaiting_generation() == []


async def test_run_once_uses_the_childs_own_age():
    exercises, profiles = _make_repos()
    profiles.create(_profile("child-1", age=9))
    exercises.create(_exercise("e1"))
    llm = _FakeLLM("QUESTION: Why did the cat sit there?")
    conversation = ConversationService(llm)

    await run_once(exercises, profiles, conversation)

    _messages, system_prompt = llm.calls[0]
    assert "9" in system_prompt


async def test_run_once_falls_back_to_a_default_age_with_no_profile():
    """The exercise's child profile may have been deleted, or the
    worker ran before it was ever created -- doesn't crash, just uses
    the same default age _run_reading_partner() itself falls back to."""
    exercises, profiles = _make_repos()
    exercises.create(_exercise("e1", child_profile_id="no-such-child"))
    llm = _FakeLLM("QUESTION: Where did the cat sit?")
    conversation = ConversationService(llm)

    processed = await run_once(exercises, profiles, conversation)

    assert processed == 1
    saved = exercises.list_for_child("no-such-child")[0]
    assert saved.comprehension_status == "generated"
