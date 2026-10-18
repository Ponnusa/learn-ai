"""Bayesian Knowledge Tracing mastery model (decision 0051) -- ported
near-verbatim from phono-storyforge's app/skills/mastery.py (Apache 2.0).
Turns per-grapheme read-aloud evidence (from alignment.py's miscue
attribution) into an updated knowledge state. Pure math, no LLM, no
dependencies beyond curriculum.py's BKT parameters and schema.py's
dataclasses.

BKT models each grapheme as a latent binary known/not-known state with
a 4-parameter model (p_init, p_transit, p_slip, p_guess). Each observed
opportunity updates the posterior P(L) via Bayes, then a learning
transition accounts for the chance the practice itself taught the skill.
"""
from .curriculum import GRAPHEME_LEVEL, MASTERY_THRESHOLD, bkt_params_for_level
from .schema import GraphemeDelta, GraphemeMastery, MasteryDelta, ReadingProfile

# grapheme -> per-opportunity outcomes (True = read correctly).
GraphemeEvidence = dict[str, list[bool]]


def _bkt_step(p_known: float, correct: bool, params: dict[str, float]) -> float:
    """Applies one BKT observation: Bayesian posterior + learning transition."""
    slip = params["p_slip"]
    guess = params["p_guess"]
    transit = params["p_transit"]

    if correct:
        numerator = p_known * (1.0 - slip)
        denominator = numerator + (1.0 - p_known) * guess
    else:
        numerator = p_known * slip
        denominator = numerator + (1.0 - p_known) * (1.0 - guess)

    posterior = numerator / denominator if denominator > 0 else p_known
    return posterior + (1.0 - posterior) * transit


def update_from_evidence(
    profile: ReadingProfile,
    grapheme_evidence: GraphemeEvidence,
    *,
    session_index: int | None = None,
    threshold: float = MASTERY_THRESHOLD,
) -> MasteryDelta:
    """Updates a learner's mastery in place from a batch of grapheme
    evidence. For each grapheme with observations, applies a BKT step
    per opportunity (in order), records correct/opportunity counts, and
    stamps the session index for spaced review. Graphemes absent from
    the profile are created on demand from the inventory."""
    levels_mastered_before = set(profile.mastered_levels(threshold))

    changes: list[GraphemeDelta] = []
    newly_mastered: list[str] = []

    for grapheme, observations in grapheme_evidence.items():
        if not observations:
            continue

        level = GRAPHEME_LEVEL.get(grapheme, "")
        params = bkt_params_for_level(level)

        mastery = profile.masteries.get(grapheme)
        if mastery is None:
            mastery = GraphemeMastery(grapheme=grapheme, level=level, p_mastery=params["p_init"])
            profile.masteries[grapheme] = mastery

        p_before = mastery.p_mastery
        was_mastered = p_before >= threshold

        p = p_before
        n_correct = 0
        for correct in observations:
            p = _bkt_step(p, correct, params)
            if correct:
                n_correct += 1

        mastery.p_mastery = p
        mastery.opportunities += len(observations)
        mastery.correct += n_correct
        if session_index is not None:
            mastery.last_seen_session = session_index

        changes.append(
            GraphemeDelta(
                grapheme=grapheme,
                level=level,
                p_before=p_before,
                p_after=p,
                n_correct=n_correct,
                n_incorrect=len(observations) - n_correct,
            )
        )
        if not was_mastered and p >= threshold:
            newly_mastered.append(grapheme)

    levels_mastered_after = set(profile.mastered_levels(threshold))
    newly_mastered_levels = [
        lvl
        for lvl in profile.mastered_levels(threshold)
        if lvl in (levels_mastered_after - levels_mastered_before)
    ]

    return MasteryDelta(
        changes=changes,
        newly_mastered=newly_mastered,
        newly_mastered_levels=newly_mastered_levels,
    )
