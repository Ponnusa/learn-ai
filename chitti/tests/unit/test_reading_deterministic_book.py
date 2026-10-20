"""Unit tests for companion_robot.reading.deterministic_book --
decision 0077's guaranteed-decodable, offline fallback book builder
(ported from phono-storyforge's eval/book_builder.py, Apache 2.0)."""
from companion_robot.reading.curriculum import GRAPHEME_INVENTORY, LEVEL_SEQUENCE
from companion_robot.reading.decodability import is_word_decodable
from companion_robot.reading.deterministic_book import build_deterministic_book
from companion_robot.reading.planner import select_objective
from companion_robot.reading.schema import Objective, ReadingProfile


def _fresh_objective() -> Objective:
    return select_objective(ReadingProfile.new("child-1"))  # targets 'a', short_vowels


def _budget_for(objective: Objective) -> list[str]:
    budget = list(objective.mastered_levels)
    if objective.target_level not in budget:
        budget.append(objective.target_level)
    return budget


def _assert_fully_decodable(book, budget: list[str]) -> None:
    for raw_word in book.words:
        cleaned = raw_word.strip(".").lower()
        if cleaned in book.sight_words:
            continue
        assert is_word_decodable(cleaned, budget), f"{cleaned!r} not decodable at {budget!r}"


def test_build_deterministic_book_is_fully_decodable_for_a_fresh_profile():
    objective = _fresh_objective()
    book = build_deterministic_book(objective)
    _assert_fully_decodable(book, _budget_for(objective))


def test_build_deterministic_book_is_fully_decodable_across_every_curriculum_grapheme():
    """The whole point: this must never produce an undecodable word,
    for any objective a real session could ever reach -- checked
    against the real cumulative budget each grapheme is introduced
    under (every earlier level mastered, plus its own)."""
    for grapheme, level in GRAPHEME_INVENTORY:
        mastered = LEVEL_SEQUENCE[: LEVEL_SEQUENCE.index(level)]
        objective = Objective(target_grapheme=grapheme, target_level=level, mastered_levels=mastered)
        book = build_deterministic_book(objective)
        assert book.pages, f"no pages produced for target {grapheme!r}"
        _assert_fully_decodable(book, mastered + [level])


def test_build_deterministic_book_never_raises():
    """No LLM call, no network -- there is nothing in this path that
    can raise BookGenerationError or anything else."""
    objective = _fresh_objective()
    book = build_deterministic_book(objective)
    assert book.generation_source == "deterministic_fallback"


def test_build_deterministic_book_pages_end_with_terminal_punctuation():
    """So sentences.split_into_sentences() -- and everything built on
    top of it (decision 0067's per-sentence loop) -- segments this
    the same way it segments any other book."""
    book = build_deterministic_book(_fresh_objective())
    assert book.pages
    assert all(page.endswith(".") for page in book.pages)


def test_build_deterministic_book_titles_with_the_interest_when_given():
    book = build_deterministic_book(_fresh_objective(), interest="dinosaurs")
    assert "Dinosaurs" in book.title


def test_build_deterministic_book_titles_generically_without_interest():
    book = build_deterministic_book(_fresh_objective())
    assert book.title == "The A Words"


def test_build_deterministic_book_prefers_decodable_words_from_the_source_passage():
    """Decision 0077: a guaranteed-decodable fallback still keeps a
    loose thread back to what the child was actually just reading,
    by preferring the parent passage's own decodable words as filler
    over the generic corpus."""
    objective = _fresh_objective()  # targets 'a', short_vowels
    book = build_deterministic_book(
        objective, source_passage="The frog jumps over the log.", length=20
    )
    # "log" is decodable at short_vowels and appears in the passage --
    # it should have been pulled in as filler.
    assert "log" in book.words


def test_build_deterministic_book_is_deterministic_for_the_same_session_index():
    objective = _fresh_objective()
    first = build_deterministic_book(objective, session_index=3)
    second = build_deterministic_book(objective, session_index=3)
    assert first.pages == second.pages


def test_build_deterministic_book_varies_across_session_indices():
    objective = _fresh_objective()
    first = build_deterministic_book(objective, session_index=0)
    second = build_deterministic_book(objective, session_index=5)
    assert first.pages != second.pages
