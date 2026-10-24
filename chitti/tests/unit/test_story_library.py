"""Unit tests for companion_robot.reading.story_library -- the
vendored Open Phonics story library and its selection logic
(decision 0104).
"""
from companion_robot.reading.schema import GraphemeMastery, Objective, ReadingProfile
from companion_robot.reading.story_library import (
    PHASES,
    _LIBRARY_STORIES,
    get_story,
    mastery_color_for_story,
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


def test_all_vendored_stories_have_a_description_and_target_words():
    """Decision 0107's own fields -- vendored alongside the rest of
    the content in decision 0104's conversion, not reinvented."""
    for story in _LIBRARY_STORIES:
        assert story.description
        assert story.words
        assert all(isinstance(word, str) and isinstance(lesson, int) for word, lesson in story.words)


def test_library_story_text_property_joins_its_own_pages():
    story = get_story("sam-sat")
    assert story.text == "Sam sat. Sam sat at the mat. A rat sat at the mat. Sam is mad at the rat."


def test_get_story_finds_a_known_slug():
    story = get_story("sam-sat")
    assert story is not None
    assert story.title == "Sam Sat"


def test_get_story_returns_none_for_an_unknown_slug():
    assert get_story("does-not-exist") is None


def _profile_with_masteries(graphemes: dict[str, float]) -> ReadingProfile:
    profile = ReadingProfile.new("child-1")
    for grapheme, p_mastery in graphemes.items():
        profile.masteries[grapheme] = GraphemeMastery(
            grapheme=grapheme, level="short_vowels", p_mastery=p_mastery,
        )
    return profile


def test_mastery_color_for_story_is_green_when_every_grapheme_is_mastered():
    story = get_story("sam-sat")
    profile = _profile_with_masteries(
        {g: 0.99 for g in ["a", "d", "e", "i", "m", "r", "s", "t", "th"]}
    )
    assert mastery_color_for_story(story, profile) == "green"


def test_mastery_color_for_story_is_red_for_a_fresh_untracked_profile():
    story = get_story("sam-sat")
    profile = ReadingProfile.new("child-1")  # every grapheme at its low BKT prior
    assert mastery_color_for_story(story, profile) == "red"


def test_mastery_color_for_story_is_yellow_for_one_weak_but_tracked_grapheme():
    story = get_story("sam-sat")
    profile = _profile_with_masteries(
        {g: 0.99 for g in ["a", "d", "e", "i", "m", "r", "s", "t", "th"]}
    )
    profile.masteries["th"].p_mastery = 0.7
    assert mastery_color_for_story(story, profile) == "yellow"
