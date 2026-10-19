"""Post-reading comprehension questions (decision 0059) -- asks the
child about the story just read and reacts warmly to their answer,
grounded only in the story's own text.

Architecturally different from every other reading/ module: alignment.py's
assess(), hints.py, and word_game.py are all deterministic diffs
against an exact expected string. An open-ended "why are they happy?"
has no single correct string to diff against -- grading it exactly
isn't the right tool, so this reuses the pattern conversation/service.py's
story_companion_reply() already established (decision 0017): ground an
LLM response in ONLY the story's own text, and react rather than
grade. This module only builds prompts and parses the strict reply
format, same split book_generation.py already uses between its own
_build_prompt()/parse_story_draft() and ConversationService holding
the real LanguageModelBackend call.

Decision 0062: found live -- the original reaction prompt revealed
the correct detail immediately on a wrong answer, with no acknowledge-
then-clue-then-retry step at all. build_reaction_prompt() now takes
which attempt this is, and asks the model to withhold the answer (one
small clue instead) unless it's the final attempt -- bounded to
exactly one retry per question, not an open-ended dialogue.
"""
from dataclasses import dataclass


def build_question_prompt(story_text: str, num_questions: int, age: int | None) -> str:
    """Asks for a mix of simple factual recall and one gentle "why"/
    "how did they feel" question, grounded in the story text only."""
    age_line = f"The child is about {age} years old. " if age else ""
    return (
        f"{age_line}You are Chitti, a friendly companion robot. A child just "
        f"read this story out loud to you. Write {num_questions} short "
        "comprehension questions about it -- simple factual recall (what a "
        "character saw, did, or said) and, if the story supports it, one "
        "gentle 'why' or 'how did they feel' question. Use ONLY what's in "
        "the story text below -- never invent details that aren't in it. "
        "Keep each question to one short, simple sentence a young child "
        "can understand.\n\n"
        'Reply with exactly one line per question, each starting with "QUESTION:", '
        "nothing else.\n\n"
        f"STORY:\n{story_text}"
    )


@dataclass
class ComprehensionReaction:
    """Decision 0062: the parsed reaction to one comprehension-answer
    attempt. `needs_retry` is the routing signal voice_loop_demo.py
    uses to decide whether to capture one more attempt -- never a
    grade spoken to the child; `text` itself is always warm regardless."""

    text: str
    needs_retry: bool


def build_reaction_prompt(
    story_text: str,
    question: str,
    child_answer: str,
    age: int | None,
    *,
    attempt_number: int = 1,
    max_attempts: int = 2,
) -> str:
    """Asks for ONE short, warm reaction to what the child said --
    explicitly not a grade, grounded in the story text only. On any
    attempt before the last, withholds the correct detail in favor of
    one small clue and a retry invitation; on the last attempt,
    explains the real detail itself and moves on -- never asks for
    another try."""
    age_line = f"The child is about {age} years old. " if age else ""
    if attempt_number >= max_attempts:
        guidance = (
            "This is the child's last attempt at this question. If their answer "
            "is already right (even in different words), just celebrate it. If "
            "it's still not right, gently explain the real detail yourself in "
            "one short sentence and move on -- do NOT ask them to try again."
        )
    else:
        guidance = (
            "If their answer is right (even in different words), celebrate it. "
            "If it's wrong or clearly incomplete, do NOT reveal the correct "
            "detail yet -- acknowledge what they said, give ONE small clue "
            "grounded in the story, and invite them to try again."
        )
    return (
        f"{age_line}You are Chitti, a friendly companion robot. You just asked "
        f'a child this question about a story they read: "{question}". They '
        f'answered: "{child_answer}". {guidance} Use ONLY what\'s in the story '
        "text below for any facts you mention. Keep it to one or two sentences, "
        "simple and encouraging either way.\n\n"
        "Reply with exactly two lines:\n"
        'STATUS: "resolved" if nothing more is needed, or "needs_retry" if you '
        "just gave a clue and are waiting on another try.\n"
        "SAY: the one short sentence to speak to the child.\n\n"
        f"STORY:\n{story_text}"
    )


def parse_questions(reply_text: str) -> list[str]:
    """Parses the QUESTION:-per-line format build_question_prompt()
    asks for. Deterministic, strict-but-forgiving (ignores blank
    lines and stray whitespace, case-insensitive on the label), same
    precedent book_generation.py's parse_story_draft() already set."""
    questions: list[str] = []
    for line in reply_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("QUESTION:"):
            question = line.split(":", 1)[1].strip()
            if question:
                questions.append(question)
    return questions


def parse_comprehension_reaction(reply_text: str) -> ComprehensionReaction:
    """Parses the STATUS:/SAY: format build_reaction_prompt() asks
    for. Same strict-but-forgiving style as parse_questions() --
    case-insensitive labels, blank lines ignored. Defaults to
    resolved=True (needs_retry=False) if the status line is missing
    or doesn't say "needs_retry" -- a parse hiccup must never get the
    child stuck in a retry loop; it just moves on instead."""
    needs_retry = False
    say = ""
    for line in reply_text.splitlines():
        line = line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("STATUS:"):
            needs_retry = "needs_retry" in line.lower()
        elif upper.startswith("SAY:"):
            say = line.split(":", 1)[1].strip()
    if not say:
        # Same "never leave the child with silence" instinct as
        # safety/checks.py's decline_message() -- a malformed reply
        # must never mean nothing gets said.
        return ComprehensionReaction(text="Thanks for sharing that!", needs_retry=False)
    return ComprehensionReaction(text=say, needs_retry=needs_retry)
