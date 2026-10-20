"""Unit tests for companion_robot.reading.sentences -- deterministic
sentence splitting and the passage-position key (decision 0067)."""
from companion_robot.reading.sentences import passage_key, split_into_sentences


def test_split_into_sentences_splits_on_terminal_punctuation():
    text = "A little bunny hops. It sees a carrot! Does it eat it?"
    assert split_into_sentences(text) == [
        "A little bunny hops.",
        "It sees a carrot!",
        "Does it eat it?",
    ]


def test_split_into_sentences_returns_one_item_for_a_single_sentence():
    assert split_into_sentences("A cat sat.") == ["A cat sat."]


def test_split_into_sentences_handles_no_terminal_punctuation_at_all():
    """No sentence-ending punctuation at all -- the whole thing is one
    sentence, not zero."""
    assert split_into_sentences("a cat sat") == ["a cat sat"]


def test_split_into_sentences_drops_empty_whitespace():
    assert split_into_sentences("   \n  ") == []
    assert split_into_sentences("") == []


def test_split_into_sentences_tolerates_extra_whitespace_between_sentences():
    text = "A cat sat.\n\nA cat ran.   A cat ate."
    assert split_into_sentences(text) == ["A cat sat.", "A cat ran.", "A cat ate."]


def test_passage_key_is_stable_for_the_same_text():
    assert passage_key("A cat sat.") == passage_key("A cat sat.")


def test_passage_key_differs_for_different_text():
    assert passage_key("A cat sat.") != passage_key("A dog ran.")
