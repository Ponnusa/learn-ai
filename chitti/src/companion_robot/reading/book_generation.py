"""Verifier-gated LLM book generation (decision 0051) -- keeps the same
*pattern* as phono-storyforge's app/tutor/llm_book.py (Apache 2.0):

    propose (LLM) -> prove (check_decodability + target-exercise) ->
    feed the violations back into the prompt -> repeat.

but rebuilt, not ported: the source calls Gemini directly and has no
content-safety step at all. Here the proposer is injected
(StoryProposer, mirroring the original's own seam) so this whole loop
is unit-testable offline with a fake proposer and zero network --
ConversationService.generate_decodable_book() is what wires in the
real call to Chitti's own LanguageModelBackend.

Three hard rules, the first two from the original, the third new here:
  1. NEVER return a book with a decodability violation. If no fully
     decodable draft is reached within `max_attempts`, this RAISES
     (BookGenerationError).
  2. The book must exercise the objective's target grapheme.
     Decodability is the absolute gate; on-target is best-effort -- a
     decodable-but-off-target draft is returned tagged "llm_offtarget"
     rather than discarded.
  3. NEW: every page must pass safety/checks.py's check_speech() before
     being accepted -- treated exactly like a decodability violation
     (fed back into the prompt, retried), never silently bypassed. The
     original has no equivalent of this at all.
"""
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from companion_robot.safety.checks import check_speech

from .decodability import check_decodability, decompose, inflectional_suffix
from .schema import GeneratedBook, Objective

# Human-readable description of what each phonics level licenses, so the
# writer knows the patterns it may use.
_LEVEL_HINTS: dict[str, str] = {
    "short_vowels": "short-vowel CVC/VC words only (cat, red, pin, dog, run, on, at)",
    "digraphs": "consonant digraphs sh, ch, th, wh, ck, ng, ph, qu (ship, chip, this)",
    "blends": "consonant blends (flat, stop, hand, went, drum)",
    "silent_e": "silent-e long vowels (make, like, home, cube)",
    "r_controlled": "r-controlled vowels ar, er, ir, or, ur (car, her, bird, fork)",
    "vowel_teams": "vowel teams (rain, see, boat, night, moon)",
    "glued_sounds": "welded rimes all, ang, ing, ong, ung, ank, ink, onk, unk (ball, sing, bank)",
    "y_vowel": "'y' as a vowel (my, happy)",
    "suffixes": "inflectional endings -s, -es, -ed, -ing on a decodable base (dogs, jumped)",
}


class BookGenerationError(RuntimeError):
    """Raised when no safe, fully decodable book was produced in time."""


@dataclass
class StoryDraft:
    """One raw proposal from the LLM, before any verification."""

    title: str
    pages: list[str]


# A StoryProposer turns a writer prompt into a draft. Async, unlike the
# original project's sync Gemini call -- every LLM call in this
# codebase is async (companion_robot.voice.interfaces.LanguageModelBackend).
# The real implementation (ConversationService.generate_decodable_book)
# calls Chitti's own LanguageModelBackend; tests inject a deterministic
# async fake.
StoryProposer = Callable[[str], Awaitable[StoryDraft]]


def _grapheme_keys(word: str) -> set[str]:
    """All inventory keys a word exercises, including the structural
    sentinels -- reuses decompose() so this agrees with the rest of
    the package."""
    d = decompose(word)
    keys = {g.grapheme for g in d.graphemes}
    gs = d.graphemes
    if any(gs[i].kind == "C" and gs[i + 1].kind == "C" for i in range(len(gs) - 1)):
        keys.add("_blend_")
    suffix = inflectional_suffix(d.word)
    if suffix:
        keys.add(f"-{suffix}")
    return keys


def _phonics_profile(objective: Objective, sight_words: set[str]) -> dict:
    return {
        "mastered_levels": list(objective.mastered_levels),
        "target_level": objective.target_level,
        "sight_words": list(sight_words),
    }


def _exercises_target(pages: list[str], target_grapheme: str) -> bool:
    return any(
        target_grapheme in _grapheme_keys(w) for page in pages for w in page.split()
    )


def _build_prompt(
    objective: Objective,
    *,
    sight_words: set[str],
    length: int,
    interest: str,
    age: int,
    feedback: str,
    source_passage: str | None = None,
) -> str:
    """Builds the writer prompt for one attempt, folding in any prior
    feedback. Decision 0068: when `source_passage` is given (a parent-
    uploaded exercise the child just finished reading), the opening
    instruction asks for a themed follow-up built on that passage's own
    topic and vocabulary instead of the child's generic stored
    interest -- reusing this exact verifier-gated loop (decodability +
    safety), not a separate generation path."""
    budget = list(objective.mastered_levels)
    if objective.target_level not in budget:
        budget.append(objective.target_level)
    allowed = "\n".join(f"  - {lvl}: {_LEVEL_HINTS.get(lvl, lvl)}" for lvl in budget)
    review = ", ".join(objective.review_graphemes) or "none"
    sight = ", ".join(sorted(sight_words)) or "none"

    if source_passage:
        opening = (
            f"Write a short decodable follow-up practice story of about {length} "
            "words across 3-5 short pages (1-2 simple sentences each) for a child "
            f"who is {age} years old. The child just read this passage -- build on "
            "it as a natural companion story, reusing its topic and some of the "
            "same words where you can, but don't just repeat it word-for-word:\n"
            f'"{source_passage}"\n'
            "Warm, gentle, age-appropriate -- never scary, violent, or sad."
        )
    else:
        theme = interest.strip() or "a friendly everyday adventure"
        opening = (
            f"Write a short decodable practice story of about {length} words across "
            "3-5 short pages (1-2 simple sentences each) for a child who is "
            f"{age} years old and loves {theme}. Warm, gentle, age-appropriate -- "
            "never scary, violent, or sad."
        )

    parts = [
        "You are Chitti, a friendly companion robot helping a child practice reading.",
        opening,
        "",
        f"FOCUS SOUND (must appear): the '{objective.target_grapheme}' grapheme "
        f"(phonics level '{objective.target_level}'). Use several words that "
        "clearly contain this sound.",
        f"Also gently revisit these review sounds if natural: {review}.",
        "",
        "DECODABILITY BUDGET -- every word must be decodable using ONLY these "
        "phonics levels:",
        allowed,
        f"Sight words the child also knows (always allowed): {sight}.",
        "Common little connector words (the, a, and, is, on, in, it) are fine.",
        "Do NOT use any word that needs a phonics pattern outside the budget "
        "above unless it is one of the allowed sight words.",
        "",
        "Respond in EXACTLY this format, nothing else, no markdown:",
        "TITLE: <the book title>",
        "PAGE: <page 1 text>",
        "PAGE: <page 2 text>",
        "(one PAGE line per page, 3-5 PAGE lines total)",
    ]
    if feedback:
        parts += [
            "",
            "REVISION REQUIRED -- your previous draft failed a check. Fix it: " + feedback,
        ]
    return "\n".join(parts)


def parse_story_draft(reply_text: str) -> StoryDraft:
    """Parses the TITLE:/PAGE: format _build_prompt() asks the LLM for.
    Deterministic, strict-but-forgiving (ignores blank lines, stray
    whitespace, and is case-insensitive on the labels) -- same "ask for
    an exact simple format, parse it strictly" precedent
    ConversationService.classify_intent() already established, chosen
    instead of JSON since this backend has no structured-output mode
    the way the original project's Gemini client does."""
    title = ""
    pages: list[str] = []
    for line in reply_text.splitlines():
        line = line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
        elif upper.startswith("PAGE:"):
            page = line.split(":", 1)[1].strip()
            if page:
                pages.append(page)
    return StoryDraft(title=title, pages=pages)


async def generate_decodable_book(
    objective: Objective,
    *,
    proposer: StoryProposer,
    session_index: int = 0,
    sight_words: set[str] | None = None,
    num_target: int = 6,
    length: int = 16,
    interest: str = "",
    age: int = 6,
    rng: random.Random | None = None,
    max_attempts: int = 4,
    source_passage: str | None = None,
) -> GeneratedBook:
    """Generates a safe, fully decodable book for an objective,
    verifier-gated. Loops propose -> prove -> feed-back until a draft
    passes every check, then returns it. Tags the result "llm" if it
    also exercises the target grapheme, or "llm_offtarget" otherwise.
    Raises BookGenerationError if nothing safe and decodable is
    produced within `max_attempts`.

    `source_passage` (decision 0068): when given, themes the story on
    that passage's own topic/vocabulary instead of `interest` -- see
    _build_prompt(). `interest` is simply ignored in that case, not an
    error; callers don't need to omit it themselves.
    """
    sight = set(sight_words or set())
    profile = _phonics_profile(objective, sight)

    feedback = ""
    best_decodable: StoryDraft | None = None
    for _attempt in range(max_attempts):
        prompt = _build_prompt(
            objective,
            sight_words=sight,
            length=length,
            interest=interest,
            age=age,
            feedback=feedback,
            source_passage=source_passage,
        )
        draft = await proposer(prompt)
        pages = [p for p in (draft.pages or []) if p and p.strip()]

        check = check_decodability("\n".join(pages), profile)
        if not check["is_decodable"]:
            feedback = f"replace or remove these words, which aren't decodable yet: {', '.join(check['violations'])}"
            continue

        # Decision 0051, not in the original: every page must also pass
        # the same safety screening every other spoken Chitti line does.
        unsafe = next((p for p in pages if not check_speech(p).allowed), None)
        if unsafe is not None:
            feedback = "the story contained content that isn't appropriate for a child -- write something different"
            continue

        on_target = _exercises_target(pages, objective.target_grapheme)
        if on_target:
            return GeneratedBook(
                title=draft.title or f"The {objective.target_grapheme} Story",
                pages=pages,
                target_grapheme=objective.target_grapheme,
                objective=objective,
                sight_words=sight,
                generation_source="llm",
            )
        if best_decodable is None:
            best_decodable = draft
        feedback = (
            f"the story is decodable but uses no word with the focus sound "
            f"'{objective.target_grapheme}' -- add some"
        )

    if best_decodable is not None:
        pages = [p for p in best_decodable.pages if p and p.strip()]
        return GeneratedBook(
            title=best_decodable.title or f"The {objective.target_grapheme} Story",
            pages=pages,
            target_grapheme=objective.target_grapheme,
            objective=objective,
            sight_words=sight,
            generation_source="llm_offtarget",
        )

    raise BookGenerationError(
        f"No safe, fully decodable book was produced for target "
        f"'{objective.target_grapheme}' within {max_attempts} attempts; "
        f"last feedback: {feedback}"
    )
