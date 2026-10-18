"""Unit tests for companion_robot.reading.planner -- the adaptive
objective selection."""
from companion_robot.reading.mastery import update_from_evidence
from companion_robot.reading.planner import select_objective
from companion_robot.reading.schema import ReadingProfile


def test_fresh_profile_targets_the_first_grapheme():
    profile = ReadingProfile.new("child-1")
    objective = select_objective(profile)
    assert objective.target_grapheme == "a"  # first in GRAPHEME_INVENTORY
    assert objective.target_level == "short_vowels"


def test_target_advances_once_the_current_one_is_mastered():
    profile = ReadingProfile.new("child-1")
    update_from_evidence(profile, {"a": [True] * 10}, session_index=0)

    objective = select_objective(profile, session_index=1)

    assert objective.target_grapheme != "a"


def test_rationale_mentions_the_target_and_session_index():
    profile = ReadingProfile.new("child-1")
    objective = select_objective(profile, session_index=3)
    assert "[session 3]" in objective.rationale
    assert objective.target_grapheme in objective.rationale


def test_mastered_levels_budget_grows_as_levels_are_completed():
    profile = ReadingProfile.new("child-1")
    assert select_objective(profile).mastered_levels == []

    # Master every grapheme in short_vowels.
    from companion_robot.reading.curriculum import GRAPHEMES_BY_LEVEL

    for grapheme in GRAPHEMES_BY_LEVEL["short_vowels"]:
        update_from_evidence(profile, {grapheme: [True] * 10}, session_index=0)

    assert "short_vowels" in select_objective(profile).mastered_levels


def test_spaced_review_picks_mastered_graphemes_not_the_target():
    profile = ReadingProfile.new("child-1")
    update_from_evidence(profile, {"a": [True] * 10, "b": [True] * 10}, session_index=0)

    objective = select_objective(profile, session_index=1, num_review=2)

    assert objective.target_grapheme not in objective.review_graphemes
    assert set(objective.review_graphemes) <= {"a", "b"}


def test_num_review_zero_returns_no_review_picks():
    profile = ReadingProfile.new("child-1")
    update_from_evidence(profile, {"a": [True] * 10}, session_index=0)

    objective = select_objective(profile, session_index=1, num_review=0)

    assert objective.review_graphemes == []


def test_everything_mastered_reinforces_the_weakest():
    """Once every grapheme in the inventory is mastered, the planner
    falls back to reinforcing whichever one has the lowest P(L)."""
    from companion_robot.reading.curriculum import GRAPHEME_INVENTORY

    profile = ReadingProfile.new("child-1")
    for grapheme, _level in GRAPHEME_INVENTORY:
        update_from_evidence(profile, {grapheme: [True] * 10}, session_index=0)

    objective = select_objective(profile, session_index=1)

    assert "All tracked graphemes are mastered" in objective.rationale
