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
"""


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


def build_reaction_prompt(
    story_text: str, question: str, child_answer: str, age: int | None
) -> str:
    """Asks for ONE short, warm reaction to what the child said --
    explicitly not a grade, grounded in the story text only."""
    age_line = f"The child is about {age} years old. " if age else ""
    return (
        f"{age_line}You are Chitti, a friendly companion robot. You just asked "
        f'a child this question about a story they read: "{question}". They '
        f'answered: "{child_answer}". Say ONE short, warm reaction -- not a '
        "grade, not correct/incorrect -- that acknowledges what they said "
        "and, if it helps, gently adds the real detail from the story. Use "
        "ONLY what's in the story text below for any facts you mention. One "
        "or two sentences, simple and encouraging either way.\n\n"
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
