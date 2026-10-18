"""Unit tests for companion_robot.reading.alignment -- the miscue
grading engine."""
from companion_robot.reading.alignment import (
    CORRECT,
    HESITATION,
    INSERTION,
    OMISSION,
    SELF_CORRECTION,
    SUBSTITUTION,
    align,
    assess,
    attribute_evidence,
)


def test_align_perfect_read_is_all_correct():
    ops = align("cat sat mat", "cat sat mat")
    assert all(op.kind == CORRECT for op in ops)


def test_align_detects_substitution():
    ops = align("cat sat mat", "cat sit mat")
    kinds = [op.kind for op in ops]
    assert SUBSTITUTION in kinds
    sub = next(op for op in ops if op.kind == SUBSTITUTION)
    assert sub.expected == "sat"
    assert sub.spoken == "sit"


def test_align_detects_omission():
    ops = align("cat sat mat", "cat mat")
    assert any(op.kind == OMISSION and op.expected == "sat" for op in ops)


def test_align_detects_insertion():
    """"really" has nothing in common with the next expected word
    ("mat"), so it's a genuine extra word, not a self-correction
    attempt (that needs surface similarity to the following word)."""
    ops = align("cat mat", "cat really mat")
    assert any(op.kind == INSERTION and op.spoken == "really" for op in ops)


def test_align_detects_hesitation_as_a_repeated_word():
    """Expected "cat sat", spoken "cat cat sat" -- the repeated "cat" is
    a hesitation, not an insertion, and doesn't count as an error."""
    ops = align("cat sat", "cat cat sat")
    assert any(op.kind == HESITATION for op in ops)
    assert all(op.kind != INSERTION for op in ops)


def test_align_detects_self_correction():
    """Expected "cat", spoken "cot cat" -- a surface-similar false
    start immediately followed by the correct word."""
    ops = align("cat", "cot cat")
    assert any(op.kind == SELF_CORRECTION for op in ops)


def test_attribute_evidence_perfect_read_is_all_true():
    ops = align("cat", "cat")
    evidence = attribute_evidence(ops)
    assert all(all(obs) for obs in evidence.values())
    assert evidence["c"] == [True]
    assert evidence["a"] == [True]
    assert evidence["t"] == [True]


def test_attribute_evidence_omission_is_all_false():
    ops = align("cat", "")
    evidence = attribute_evidence(ops)
    assert evidence["c"] == [False]


def test_attribute_evidence_sight_word_contributes_nothing():
    ops = align("the", "the")
    evidence = attribute_evidence(ops, sight_words={"the"})
    assert evidence == {}  # sight words are memorized, not decoded


def test_attribute_evidence_blend_sentinel():
    """Adjacent consonant graphemes ('s' + 't' in "stop") produce one
    _blend_ observation in addition to the per-letter ones."""
    ops = align("stop", "stop")
    evidence = attribute_evidence(ops)
    assert evidence["_blend_"] == [True]


def test_attribute_evidence_suffix_sentinel():
    ops = align("jumps", "jumps")
    evidence = attribute_evidence(ops)
    assert evidence["-s"] == [True]


def test_assess_accuracy_and_wcpm():
    result = assess("cat sat mat", "cat sat mat", duration_seconds=3.0)
    assert result.accuracy == 1.0
    assert result.wcpm == 60.0  # 3 words in 3 seconds -> 60 WCPM
    assert result.errors == 0


def test_assess_counts_errors_correctly():
    result = assess("cat sat mat", "cat sit mat", duration_seconds=3.0)
    assert result.substitutions == 1
    assert result.errors == 1
    assert result.accuracy < 1.0


def test_assess_self_correction_and_hesitation_are_not_errors():
    result = assess("cat sat", "cat cat sat", duration_seconds=2.0)
    assert result.errors == 0
    assert result.accuracy == 1.0


def test_assess_miscues_list_excludes_correct_ops():
    result = assess("cat sat mat", "cat sit mat", duration_seconds=3.0)
    assert all(m.kind != CORRECT for m in result.miscues)
    assert len(result.miscues) == 1


def test_assess_correct_words_lists_only_the_correctly_read_words():
    """Decision 0055: feedback.py cites a specific real word the child
    read correctly as evidence -- this is where that list comes from."""
    result = assess("cat sat mat", "cat sit mat", duration_seconds=3.0)
    assert result.correct_words == ["cat", "mat"]  # "sat" was substituted
