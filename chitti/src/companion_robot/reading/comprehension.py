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

Decision 0083, found live: the model itself is the only judge of
whether an answer is right -- there's no story-grounded check at all.
A real transcript caught it rejecting an answer ("red," for "What
color is Dan's dog?" against a story that says "Dan has a red dog")
with a clue that didn't even make sense ("the dog has a color more
commonly found in nature"), then admitting on the final attempt that
"red" was right all along. `answer_matches_story_text()` is a cheap,
deterministic safety net for exactly that failure shape -- it can't
know an answer is *correct* in general (that's still the model's
job), but a literal word-for-word match against the story text is a
strong, checkable signal the model's own rejection shouldn't be
trusted.
"""
import re
from dataclasses import dataclass

from .decodability import clean_word

# Decision 0083: a word has to be long enough to be a real signal, not
# noise -- same threshold hints.py's own is_worth_practicing() uses
# for "substantial enough to matter," so "a"/"is"/"the" (in the
# child's answer, in the story, or both) never falsely look like a
# match.
_MIN_MATCH_WORD_LENGTH = 3

# Decision 0083: spoken when a literal match overrides a model's own
# "needs_retry" -- deliberately generic and never built from the
# model's own (possibly self-contradicting) clue text, since that text
# was written on the assumption the answer was wrong.
LITERAL_MATCH_AFFIRMATION = "Yes, that's it! Great job remembering that from the story."


def answer_matches_story_text(answer: str, story_text: str) -> bool:
    """True if a substantial word (3+ letters) in `answer` appears,
    whole, in `story_text` -- see the module docstring's decision 0083
    note. Deliberately lenient (a shared word is treated as a signal
    worth trusting over the model, not proof of correctness) -- the
    failure this guards against (telling a child a story-grounded
    answer is wrong) is worse than the one it risks (being too easy
    on an answer that merely shares a word with the text), consistent
    with this codebase's existing "when in doubt, don't make the
    child feel wrong" bar elsewhere (the hint ladder's no-penalty
    retries, the word game's always-upbeat closing)."""
    story_words = {clean_word(w) for w in re.findall(r"[A-Za-z']+", story_text)}
    answer_words = {
        clean_word(w) for w in re.findall(r"[A-Za-z']+", answer) if len(w) >= _MIN_MATCH_WORD_LENGTH
    }
    return bool(answer_words & story_words)


# Decision 0097, found live: the model marked a reaction "STATUS:
# resolved" -- so the loop didn't ask for another attempt -- but its
# own SAY text still read like an unresolved clue ("Great job! The
# hen did sit on something, but think about what that something was
# again!") against a story that literally says "A hen sat on a log,"
# for the answer "Log." The literal-match override below only fired
# for "needs_retry" verdicts (decision 0083); a "resolved" verdict
# with contradictory, still-asking-to-reconsider text slipped
# through both checks and reached the child as-is. This phrase list
# is a second, narrow trigger for exactly that shape -- a "resolved"
# response whose own wording still invites another attempt -- not
# exhaustive, but covers the common ways a model hedges like this.
_RETRY_INVITATION_PHRASES = (
    "try again",
    "try that again",
    "try once more",
    "one more try",
    "think again",
    "think about",
    "what do you think",
    "can you think",
)


def sounds_like_a_retry_invitation(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _RETRY_INVITATION_PHRASES)


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
    evidence_sentence: str | None = None,
) -> str:
    """Asks for ONE short, warm reaction to what the child said --
    explicitly not a grade, grounded in the story text only. On any
    attempt before the last, withholds the correct detail in favor of
    one small clue and a retry invitation; on the last attempt,
    explains the real detail itself and moves on -- never asks for
    another try.

    Decision 0126: `evidence_sentence` (story_library.py's own
    pre-written question/evidence pairs, decision 0104) is the one
    story line that directly answers this question, when known --
    passed through so a correct answer's confirmation can point at
    that real line ("the story tells us...") instead of a generic
    "nice work," and so the model can tell a plain factual-recall
    question apart from an open-ended inference one (e.g. "how do
    they feel?") with no single line like that -- those get
    encouraged as good thinking, not confirmed as if the story said
    so outright."""
    age_line = f"The child is about {age} years old. " if age else ""
    evidence_line = (
        f'The one line in the story that directly answers this is: "{evidence_sentence}". '
        "When their answer is right, point to that as where it comes from in the story. "
        if evidence_sentence
        else "This question has no single right line in the story -- it's asking for "
        "the child's own reasonable idea, not a fact to confirm. When they give a "
        "sensible answer, encourage it as good thinking rather than confirming it as "
        "something the story states outright. "
    )
    if attempt_number >= max_attempts:
        guidance = (
            "This is the child's last attempt at this question. If their answer "
            "is already right (even in different words), clearly confirm it was "
            "right -- name the actual detail they got right (don't just say "
            "something generic like \"thanks for sharing that\") -- and stop "
            "there; do not also hedge or ask them to reconsider. If it's still "
            "not right, gently explain the real detail yourself in one short "
            "sentence and move on -- do NOT ask them to try again."
        )
    else:
        guidance = (
            "If their answer is right (even in different words), clearly confirm "
            "it was right -- name the actual detail they got right (don't just say "
            "something generic like \"thanks for sharing that\") -- and stop there; "
            "do not also hedge, add a clue, or ask them to reconsider; a right "
            "answer gets STATUS resolved, full stop. If it's wrong or clearly "
            "incomplete, do NOT reveal the correct detail yet -- acknowledge what "
            "they said, give ONE small clue grounded in the story, and invite them "
            "to try again."
        )
    return (
        f"{age_line}You are Chitti, a friendly companion robot. You just asked "
        f'a child this question about a story they read: "{question}". They '
        f'answered: "{child_answer}". {evidence_line}{guidance} Use ONLY what\'s '
        "in the story text below for any facts you mention. Keep it to one or "
        "two sentences, simple and encouraging either way.\n\n"
        "Reply with exactly two lines, and make sure they agree with each "
        "other -- never mark it resolved while still asking the child to "
        "reconsider or try again, and never mark it needs_retry while also "
        "confirming or revealing the correct detail:\n"
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


def parse_comprehension_reaction(
    reply_text: str, child_answer: str = ""
) -> ComprehensionReaction:
    """Parses the STATUS:/SAY: format build_reaction_prompt() asks
    for. Same strict-but-forgiving style as parse_questions() --
    case-insensitive labels, blank lines ignored. Defaults to
    resolved=True (needs_retry=False) if the status line is missing
    or doesn't say "needs_retry" -- a parse hiccup must never get the
    child stuck in a retry loop; it just moves on instead.

    `child_answer` (passed by react_to_comprehension_answer(), which
    has it on hand) shapes the malformed-reply fallback below --
    found live, a bare "Thanks for sharing that!" with no mention of
    what the child actually said reads as flat and disengaged next to
    every other reaction in this flow, which names the real detail."""
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
        fallback = (
            f'Great job, you said "{child_answer}" -- nice work!'
            if child_answer
            else "Great job answering that!"
        )
        return ComprehensionReaction(text=fallback, needs_retry=False)
    return ComprehensionReaction(text=say, needs_retry=needs_retry)
