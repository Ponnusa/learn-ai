"""Unit tests for companion_robot.reading.story_library -- the
vendored Open Phonics story library and its selection logic
(decision 0104).
"""
from companion_robot.reading.schema import Objective
from companion_robot.reading.story_library import (
    PHASES,
    _LIBRARY_STORIES,
    pick_library_book,
    stories_by_phase,
)

_OBJECTIVE = Objective(target_grapheme="a", target_level="short_vowels")


def test_all_vendored_stories_have_a_nonempty_body_and_slug():
    assert len(_LIBRARY_STORIES) == 30
    for story in _LIBRARY_STORIES:
        assert story.slug
        assert story.pages
        assert all(story.pages)
        assert 1 <= story.phase <= 7


def test_phases_covers_every_phase_used_by_a_story():
    phase_ids = {p[0] for p in PHASES}
    used_phases = {s.phase for s in _LIBRARY_STORIES}
    assert used_phases <= phase_ids


def test_pick_library_book_returns_the_lowest_order_unread_story():
    book = pick_library_book(1, _OBJECTIVE, set())
    assert book is not None
    assert book.library_slug == "sam-sat"  # phase 1's own order=1 story
    assert book.generation_source == "story_library"
    assert book.pages == ["Sam sat.", "Sam sat at the mat.", "A rat sat at the mat.", "Sam is mad at the rat."]
    assert book.comprehension  # pre-written Q&A carried through


def test_pick_library_book_skips_already_completed_stories():
    first = pick_library_book(1, _OBJECTIVE, set())
    second = pick_library_book(1, _OBJECTIVE, {first.library_slug})
    assert second is not None
    assert second.library_slug != first.library_slug


def test_pick_library_book_returns_none_once_a_phase_is_exhausted():
    phase_1_slugs = {s.slug for s in _LIBRARY_STORIES if s.phase == 1}
    assert pick_library_book(1, _OBJECTIVE, phase_1_slugs) is None


def test_pick_library_book_returns_none_for_an_unknown_phase():
    assert pick_library_book(99, _OBJECTIVE, set()) is None


def test_pick_library_book_carries_the_objective_through_unchanged():
    book = pick_library_book(2, _OBJECTIVE, set())
    assert book.objective is _OBJECTIVE
    assert book.target_grapheme == _OBJECTIVE.target_grapheme


def test_stories_by_phase_groups_and_orders_every_story():
    grouped = stories_by_phase()
    assert set(grouped.keys()) == {p[0] for p in PHASES}
    assert sum(len(stories) for stories in grouped.values()) == len(_LIBRARY_STORIES)
    # Each phase's own stories come back sorted by their own order.
    for stories in grouped.values():
        assert [s.order for s in stories] == sorted(s.order for s in stories)
    assert [s.slug for s in grouped[1]] == ["sam-sat", "the-cat-at-the-mat", "it-is-dim"]
