"""Unit tests for companion_robot.reading.book_generation -- the
verifier-gated LLM loop, offline with a fake async proposer, no
network. Decision 0051's own addition over the ported original: the
check_speech() safety retry path.
"""
import pytest

from companion_robot.reading.book_generation import (
    BookGenerationError,
    StoryDraft,
    generate_decodable_book,
    parse_story_draft,
)
from companion_robot.reading.planner import select_objective
from companion_robot.reading.schema import ReadingProfile


def _objective():
    return select_objective(ReadingProfile.new("child-1"))  # targets 'a', short_vowels


async def test_generate_decodable_book_accepts_a_good_draft_on_first_try():
    async def proposer(prompt: str) -> StoryDraft:
        return StoryDraft(title="The Cat", pages=["A cat sat.", "A cat ran."])

    book = await generate_decodable_book(_objective(), proposer=proposer)

    assert book.title == "The Cat"
    assert book.generation_source == "llm"  # decodable AND exercises 'a'


async def test_generate_decodable_book_retries_on_decodability_violation():
    """First draft uses "ship" (needs digraphs, not yet mastered);
    second draft is fixed."""
    attempts = []

    async def proposer(prompt: str) -> StoryDraft:
        attempts.append(prompt)
        if len(attempts) == 1:
            return StoryDraft(title="Bad", pages=["A ship sat."])
        return StoryDraft(title="Good", pages=["A cat sat."])

    book = await generate_decodable_book(_objective(), proposer=proposer)

    assert len(attempts) == 2
    assert "ship" in attempts[1]  # the violation was fed back into the retry prompt
    assert book.title == "Good"


async def test_generate_decodable_book_retries_on_unsafe_content():
    """Decision 0051's own addition, not in the original: a decodable
    but unsafe draft must be rejected and retried, never silently
    accepted just because it passed the phonics check."""
    attempts = []

    async def proposer(prompt: str) -> StoryDraft:
        attempts.append(prompt)
        if len(attempts) == 1:
            # Fully decodable at this level, but profane.
            return StoryDraft(title="Bad", pages=["A cat is a damn cat."])
        return StoryDraft(title="Good", pages=["A cat sat."])

    book = await generate_decodable_book(_objective(), proposer=proposer)

    assert len(attempts) == 2
    assert book.title == "Good"


async def test_generate_decodable_book_tags_offtarget_when_never_on_target():
    """Decodable every time but never uses the target grapheme 'a' --
    still returned (safe to read), tagged "llm_offtarget" rather than
    discarded, after max_attempts."""

    async def proposer(prompt: str) -> StoryDraft:
        # "s", "t" are short_vowels consonants -- decodable -- but no 'a'.
        return StoryDraft(title="No Target", pages=["Sit. Sit."])

    book = await generate_decodable_book(_objective(), proposer=proposer, max_attempts=2)

    assert book.generation_source == "llm_offtarget"


async def test_generate_decodable_book_raises_if_never_decodable():
    async def proposer(prompt: str) -> StoryDraft:
        return StoryDraft(title="Bad", pages=["A ship sat."])  # always needs digraphs

    with pytest.raises(BookGenerationError):
        await generate_decodable_book(_objective(), proposer=proposer, max_attempts=2)


async def test_generate_decodable_book_themes_on_a_source_passage_when_given():
    """Decision 0068: a parent-uploaded exercise's own text, when
    passed as source_passage, drives the writer prompt instead of the
    generic interest -- the follow-up story is meant to build on what
    the child just read, not a new unrelated theme."""
    prompts = []

    async def proposer(prompt: str) -> StoryDraft:
        prompts.append(prompt)
        return StoryDraft(title="The Cat", pages=["A cat sat."])

    await generate_decodable_book(
        _objective(),
        proposer=proposer,
        interest="dinosaurs",  # must be ignored in favor of source_passage
        source_passage="A rat sat on a mat.",
    )

    assert "A rat sat on a mat." in prompts[0]
    assert "dinosaurs" not in prompts[0]


async def test_generate_decodable_book_uses_interest_when_no_source_passage():
    prompts = []

    async def proposer(prompt: str) -> StoryDraft:
        prompts.append(prompt)
        return StoryDraft(title="The Cat", pages=["A cat sat."])

    await generate_decodable_book(_objective(), proposer=proposer, interest="dinosaurs")

    assert "dinosaurs" in prompts[0]


def test_parse_story_draft_reads_title_and_pages():
    draft = parse_story_draft("TITLE: The Cat\nPAGE: A cat sat.\nPAGE: A cat ran.")
    assert draft.title == "The Cat"
    assert draft.pages == ["A cat sat.", "A cat ran."]


def test_parse_story_draft_ignores_blank_lines_and_is_case_insensitive():
    draft = parse_story_draft("\ntitle: The Cat\n\npage: A cat sat.\n   \n")
    assert draft.title == "The Cat"
    assert draft.pages == ["A cat sat."]


def test_parse_story_draft_handles_missing_pages_gracefully():
    draft = parse_story_draft("TITLE: Empty")
    assert draft.title == "Empty"
    assert draft.pages == []
