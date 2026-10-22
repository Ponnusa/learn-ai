"""Unit tests for companion_robot.reading.story_bank -- decision
0078's hand-written, pre-verified natural-story fallback."""
from companion_robot.reading.curriculum import GRAPHEME_INVENTORY, LEVEL_SEQUENCE
from companion_robot.reading.decodability import clean_word, is_word_decodable
from companion_robot.reading.schema import Objective
from companion_robot.reading.story_bank import _DEFAULT_SIGHT, _STORY_BANK, pick_story_bank_book


def _budget_for_level(level: str) -> list[str]:
    return LEVEL_SEQUENCE[: LEVEL_SEQUENCE.index(level) + 1]


def test_every_story_is_decodable_at_its_own_authored_level():
    """The whole point: every hand-written story must actually be
    fully decodable at the budget it claims to be written for --
    re-checked against the real engine, never trusted from authoring
    alone."""
    for story in _STORY_BANK:
        budget = _budget_for_level(story.level)
        for page in story.pages:
            for raw_word in page.split():
                cleaned = clean_word(raw_word)
                if not cleaned or cleaned in _DEFAULT_SIGHT:
                    continue
                assert is_word_decodable(cleaned, budget), (
                    f"{cleaned!r} in {story.title!r} not decodable at {budget!r}"
                )


def test_every_curriculum_level_has_at_least_one_story():
    covered_levels = {story.level for story in _STORY_BANK}
    assert covered_levels == set(LEVEL_SEQUENCE)


def test_pick_story_bank_book_finds_a_match_for_every_curriculum_grapheme():
    """Every real objective a session could ever reach must get a
    story -- checked against the real cumulative budget each
    grapheme is introduced under."""
    for grapheme, level in GRAPHEME_INVENTORY:
        mastered = LEVEL_SEQUENCE[: LEVEL_SEQUENCE.index(level)]
        objective = Objective(target_grapheme=grapheme, target_level=level, mastered_levels=mastered)
        book = pick_story_bank_book(objective)
        assert book is not None, f"no story for target {grapheme!r} ({level!r})"
        assert book.generation_source == "story_bank"
        assert book.pages


def test_pick_story_bank_book_prefers_a_story_on_the_objective_s_own_level():
    objective = Objective(target_grapheme="a", target_level="short_vowels", mastered_levels=[])
    book = pick_story_bank_book(objective, session_index=0)
    on_level_titles = {s.title for s in _STORY_BANK if s.level == "short_vowels"}
    assert book.title in on_level_titles


def test_pick_story_bank_book_rotates_across_session_indices():
    objective = Objective(target_grapheme="a", target_level="short_vowels", mastered_levels=[])
    first = pick_story_bank_book(objective, session_index=0)
    second = pick_story_bank_book(objective, session_index=1)
    assert first.title != second.title


def test_pick_story_bank_book_is_deterministic_for_the_same_session_index():
    objective = Objective(target_grapheme="a", target_level="short_vowels", mastered_levels=[])
    first = pick_story_bank_book(objective, session_index=2)
    second = pick_story_bank_book(objective, session_index=2)
    assert first.title == second.title
    assert first.pages == second.pages
