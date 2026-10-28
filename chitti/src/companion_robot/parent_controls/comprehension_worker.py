"""Decision 0131: generates comprehension questions for parent-
uploaded reading exercises up front, instead of Reading Partner
generating them live (an LLM call) the first time the child actually
reads one.

Deliberately its OWN process, separate from both voice_loop_demo.py
(Chitti's own push-to-talk loop) and parent_controls/app.py (the Flask
web UI, reachable from any device on the LAN per decision 0002) --
the Flask app has no LLM backend import anywhere in it today, and
should stay that way: it's the one surface here reachable from
outside this device, so it's the one surface that should never hold
an LLM API key. This script holds the key (same
OpenAILanguageModelBackend + config/loader.py env loading
voice_loop_demo.py already uses) and talks to the parent only through
the shared sqlite db -- same db file, same ReadingExerciseRepository,
no HTTP between this and the Flask app at all.

A plain polling loop, not a real scheduler: run_once() does one full
pass over every exercise awaiting generation and returns; main() just
calls it in a sleep loop. Meant to run under cron/systemd on the Pi
(see scripts/run_comprehension_worker.sh), independent of whether
Chitti's own voice_loop_demo.py is even running -- a parent can upload
an exercise while the child's device is off, and still see questions
to review next time they open Parent Controls.

Generated questions are NEVER used with the child until a parent
explicitly approves them (ReadingExerciseRepository.approve_questions(),
called from the Flask app) -- this worker only ever reaches
"generated," never "approved."
"""
import asyncio
import logging
import time
from pathlib import Path

from companion_robot.conversation.service import ConversationService
from companion_robot.diagnostics.logging_setup import configure_logging
from companion_robot.parent_controls.profiles import ChildProfileRepository
from companion_robot.parent_controls.reading_exercises import ReadingExerciseRepository
from companion_robot.storage.sqlite import connect
from companion_robot.voice.openai_backend import OpenAILanguageModelBackend

logger = logging.getLogger(__name__)

_DEFAULT_POLL_SECONDS = 20
# Decision 0131: matches _run_comprehension_questions()'s own
# num_questions default in voice_loop_demo.py -- same "1-2 questions"
# shape the user asked for, just generated ahead of time instead of
# live.
_NUM_QUESTIONS = 2
_DEFAULT_AGE = 6  # same fallback _run_reading_partner() itself uses when a profile has none


async def generate_for_exercise(
    exercise, conversation: ConversationService, age: int | None
) -> list[str]:
    return await conversation.generate_comprehension_questions(
        exercise.content, num_questions=_NUM_QUESTIONS, age=age or _DEFAULT_AGE
    )


async def run_once(
    exercises: ReadingExerciseRepository,
    profiles: ChildProfileRepository,
    conversation: ConversationService,
) -> int:
    """One full pass over every exercise awaiting generation. Returns
    how many were processed (generated or failed), so main()'s log
    line can say something useful even when it's 0 most cycles."""
    pending = exercises.list_awaiting_generation()
    for exercise in pending:
        profile = profiles.get(exercise.child_profile_id)
        age = profile.age if profile else None
        try:
            questions = await generate_for_exercise(exercise, conversation, age)
        except Exception:
            logger.exception(
                "comprehension generation raised for exercise %s", exercise.id
            )
            questions = []
        if questions:
            exercises.save_generated_questions(exercise.id, questions)
            logger.info(
                "generated %d comprehension question(s) for exercise %s (%r)",
                len(questions), exercise.id, exercise.title,
            )
        else:
            # Decision 0131: every candidate question got dropped by
            # check_speech() (same as generate_comprehension_questions()'s
            # own doc), or the call raised -- either way, nothing safe
            # to show a parent. Marked "failed" rather than left
            # "pending" so this exact content isn't retried every
            # single poll; a parent's "regenerate" tries again.
            exercises.mark_generation_failed(exercise.id)
            logger.warning(
                "no usable comprehension questions generated for exercise %s (%r)",
                exercise.id, exercise.title,
            )
    return len(pending)


async def _main_loop(poll_seconds: float) -> None:
    configure_logging()
    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    conn = connect(data_dir / "chitti.db")  # same db file parent_controls/app.py uses
    exercises = ReadingExerciseRepository(conn)
    profiles = ChildProfileRepository(conn)
    conversation = ConversationService(OpenAILanguageModelBackend())

    logger.info("comprehension worker started, polling every %.0fs", poll_seconds)
    while True:
        start = time.monotonic()
        processed = await run_once(exercises, profiles, conversation)
        if processed:
            logger.info(
                "comprehension worker pass: %d exercise(s) processed in %.2fs",
                processed, time.monotonic() - start,
            )
        await asyncio.sleep(poll_seconds)


def main() -> None:
    asyncio.run(_main_loop(_DEFAULT_POLL_SECONDS))


if __name__ == "__main__":
    main()
