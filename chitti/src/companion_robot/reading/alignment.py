"""Miscue analysis (decision 0051) -- ported near-verbatim from
phono-storyforge's app/skills/alignment.py (Apache 2.0). Given what a
book expected the child to read and what they actually spoke (a
transcript), deterministically:
  1. align()             -> aligns the two word streams (difflib) and
     classifies every position: correct / substitution / omission /
     insertion / self_correction / hesitation.
  2. attribute_evidence() -> diffs the grapheme decompositions of
     expected vs. spoken words to blame specific graphemes, producing
     the grapheme_evidence dict mastery.py's BKT update consumes.
  3. assess()             -> bundles miscues + fluency + evidence into
     an AssessmentResult.

Pure Python, no LLM -- builds entirely on decodability.decompose(), the
same word->grapheme map decodability checking and planning use, so
attribution and mastery share one source of truth.
"""
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from . import fluency
from .decodability import GraphemeHit, clean_word, decompose, inflectional_suffix
from .schema import AssessmentResult, Miscue

# A self-correction is recognized when the child's discarded first
# attempt is this surface-similar to the word they then read correctly.
_SELF_CORRECTION_SIMILARITY = 0.6

CORRECT = "correct"
SUBSTITUTION = "substitution"
OMISSION = "omission"
INSERTION = "insertion"
SELF_CORRECTION = "self_correction"
HESITATION = "hesitation"

# Kinds that don't count against accuracy/WCPM: the word was ultimately read.
_NON_ERROR_KINDS = frozenset({CORRECT, SELF_CORRECTION, HESITATION})


@dataclass
class AlignOp:
    """One aligned position between the expected and spoken word streams."""

    kind: str
    expected: str | None
    spoken: str | None
    position: int
    error_word: str | None = None

    @property
    def is_error(self) -> bool:
        return self.kind not in _NON_ERROR_KINDS


def tokenize(text: str | list[str]) -> list[str]:
    """Splits text into cleaned, lowercased word tokens (drops punctuation/empties)."""
    raw = text if isinstance(text, (list, tuple)) else str(text).split()
    return [c for t in raw if (c := clean_word(t))]


def _similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a, b).ratio() >= _SELF_CORRECTION_SIMILARITY


def align(expected: str | list[str], spoken: str | list[str]) -> list[AlignOp]:
    """Aligns expected vs. spoken word streams and classifies each
    position. Uses difflib's SequenceMatcher over token lists, then
    post-processes the opcodes to recover two running-record patterns
    difflib can't label on its own: hesitation/repetition (an extra
    copy of a word next to its correct reading) and self_correction (a
    wrong attempt immediately followed by the correct word, surface-
    similar to it). Both count as the word eventually being read
    correctly; only true substitutions/omissions/insertions are errors.
    """
    exp = tokenize(expected)
    spk = tokenize(spoken)
    sm = SequenceMatcher(a=exp, b=spk, autojunk=False)
    opcodes = sm.get_opcodes()

    ops: list[AlignOp] = []
    idx = 0
    n = len(opcodes)
    while idx < n:
        tag, i1, i2, j1, j2 = opcodes[idx]

        if tag == "equal":
            for k in range(i2 - i1):
                ops.append(AlignOp(CORRECT, exp[i1 + k], spk[j1 + k], i1 + k))
            idx += 1
            continue

        if tag == "delete":
            for k in range(i2 - i1):
                ops.append(AlignOp(OMISSION, exp[i1 + k], None, i1 + k))
            idx += 1
            continue

        if tag == "insert":
            if (j2 - j1) == 1:
                w = spk[j1]
                prev = opcodes[idx - 1] if idx > 0 else None
                nxt = opcodes[idx + 1] if idx + 1 < n else None
                prev_word = exp[prev[2] - 1] if prev and prev[0] == "equal" else None
                next_word = exp[nxt[1]] if nxt and nxt[0] == "equal" else None

                if w == prev_word or w == next_word:
                    pos = nxt[1] if next_word == w else prev[2] - 1
                    ops.append(AlignOp(HESITATION, w, w, pos))
                    idx += 1
                    continue
                if next_word is not None and _similar(w, next_word):
                    ops.append(
                        AlignOp(SELF_CORRECTION, next_word, next_word, nxt[1], error_word=w)
                    )
                    idx += 1
                    continue
            for k in range(j2 - j1):
                ops.append(AlignOp(INSERTION, None, spk[j1 + k], i1))
            idx += 1
            continue

        # replace: pair expected/spoken positionally; leftovers are omissions/insertions.
        exp_block = exp[i1:i2]
        spk_block = spk[j1:j2]
        for k in range(max(len(exp_block), len(spk_block))):
            e = exp_block[k] if k < len(exp_block) else None
            s = spk_block[k] if k < len(spk_block) else None
            if e is not None and s is not None:
                ops.append(AlignOp(SUBSTITUTION, e, s, i1 + k))
            elif e is not None:
                ops.append(AlignOp(OMISSION, e, None, i1 + k))
            else:
                ops.append(AlignOp(INSERTION, None, s, i2 - 1))
        idx += 1

    return ops


def _adjacent_blend_pairs(graphemes: list[GraphemeHit]) -> list[tuple[int, int]]:
    return [
        (i, i + 1)
        for i in range(len(graphemes) - 1)
        if graphemes[i].kind == "C" and graphemes[i + 1].kind == "C"
    ]


def _grapheme_correct_flags(
    exp_graphemes: list[GraphemeHit], spoken_word: str | None, sight: set[str]
) -> list[bool]:
    if spoken_word is None:
        return [False] * len(exp_graphemes)

    exp_keys = [g.grapheme for g in exp_graphemes]
    spk_keys = [g.grapheme for g in decompose(spoken_word, sight_words=sight).graphemes]
    if exp_keys == spk_keys:
        return [True] * len(exp_graphemes)

    flags = [False] * len(exp_graphemes)
    sm = SequenceMatcher(a=exp_keys, b=spk_keys, autojunk=False)
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                flags[i] = True
    return flags


def _attribute_word(
    expected_word: str, spoken_word: str | None, evidence: dict[str, list[bool]], sight: set[str]
) -> None:
    decomp = decompose(expected_word, sight_words=sight)
    if decomp.is_sight_word or not decomp.graphemes:
        return

    graphemes = decomp.graphemes
    flags = _grapheme_correct_flags(graphemes, spoken_word, sight)

    for g, ok in zip(graphemes, flags):
        evidence[g.grapheme].append(ok)

    for i, j in _adjacent_blend_pairs(graphemes):
        evidence["_blend_"].append(flags[i] and flags[j])

    suffix = inflectional_suffix(decomp.word)
    if suffix:
        start = len(decomp.word) - len(suffix)
        suffix_flags = [ok for g, ok in zip(graphemes, flags) if g.span[0] >= start]
        if suffix_flags:
            evidence[f"-{suffix}"].append(all(suffix_flags))


def attribute_evidence(ops: list[AlignOp], *, sight_words: set[str] | None = None) -> dict[str, list[bool]]:
    """Turns a classified op stream into grapheme_evidence for the mastery model."""
    sight = {clean_word(w) for w in (sight_words or set())}
    evidence: dict[str, list[bool]] = defaultdict(list)
    for op in ops:
        if op.kind == CORRECT:
            _attribute_word(op.expected, op.expected, evidence, sight)
        elif op.kind == SUBSTITUTION:
            _attribute_word(op.expected, op.spoken, evidence, sight)
        elif op.kind == OMISSION:
            _attribute_word(op.expected, None, evidence, sight)
        # self_correction/hesitation: covered by the adjacent CORRECT op.
        # insertion: no expected grapheme to attribute.
    return dict(evidence)


def assess(
    expected: str | list[str],
    spoken: str | list[str],
    *,
    duration_seconds: float,
    sight_words: set[str] | None = None,
) -> AssessmentResult:
    """Runs the full miscue analysis for one read-aloud and returns the result."""
    ops = align(expected, spoken)
    total_words = len(tokenize(expected))

    words_correct = sum(1 for op in ops if op.kind == CORRECT)
    substitutions = sum(1 for op in ops if op.kind == SUBSTITUTION)
    omissions = sum(1 for op in ops if op.kind == OMISSION)
    insertions = sum(1 for op in ops if op.kind == INSERTION)
    self_corrections = sum(1 for op in ops if op.kind == SELF_CORRECTION)

    evidence = attribute_evidence(ops, sight_words=sight_words)
    correct_words = [op.expected for op in ops if op.kind == CORRECT and op.expected]
    miscues = [
        Miscue(
            kind=op.kind,
            expected=op.expected,
            spoken=op.spoken,
            position=op.position,
            error_word=op.error_word,
        )
        for op in ops
        if op.kind != CORRECT
    ]

    return AssessmentResult(
        expected_text=expected if isinstance(expected, str) else " ".join(expected),
        spoken_text=spoken if isinstance(spoken, str) else " ".join(spoken),
        total_words=total_words,
        words_correct=words_correct,
        errors=substitutions + omissions + insertions,
        substitutions=substitutions,
        omissions=omissions,
        insertions=insertions,
        self_corrections=self_corrections,
        accuracy=fluency.accuracy(words_correct, total_words),
        wcpm=fluency.wcpm(words_correct, duration_seconds),
        duration_seconds=duration_seconds,
        miscues=miscues,
        grapheme_evidence=evidence,
        correct_words=correct_words,
    )


def merge_assessments(results: list[AssessmentResult]) -> AssessmentResult:
    """Decision 0067: combines one AssessmentResult per sentence (from
    sentence-by-sentence assess() calls) into a single result spanning
    the whole passage -- so build_reading_feedback() and the post-read
    activities keep working against one AssessmentResult the same way
    they always have, without needing to know reading happened sentence
    by sentence underneath. Every count is a straight sum; accuracy/wcpm
    are recomputed from the summed totals rather than averaged, same as
    assess() computes them from a single read's totals."""
    total_words = sum(r.total_words for r in results)
    words_correct = sum(r.words_correct for r in results)
    duration_seconds = sum(r.duration_seconds for r in results)

    merged_evidence: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        for grapheme, observations in r.grapheme_evidence.items():
            merged_evidence[grapheme].extend(observations)

    return AssessmentResult(
        expected_text=" ".join(r.expected_text for r in results),
        spoken_text=" ".join(r.spoken_text for r in results),
        total_words=total_words,
        words_correct=words_correct,
        errors=sum(r.errors for r in results),
        substitutions=sum(r.substitutions for r in results),
        omissions=sum(r.omissions for r in results),
        insertions=sum(r.insertions for r in results),
        self_corrections=sum(r.self_corrections for r in results),
        accuracy=fluency.accuracy(words_correct, total_words),
        wcpm=fluency.wcpm(words_correct, duration_seconds),
        duration_seconds=duration_seconds,
        miscues=[m for r in results for m in r.miscues],
        grapheme_evidence=dict(merged_evidence),
        correct_words=[w for r in results for w in r.correct_words],
    )
