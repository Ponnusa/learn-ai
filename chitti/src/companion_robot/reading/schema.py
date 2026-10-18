"""Reading Partner data model (decision 0051) -- plain dataclasses,
translated from phono-storyforge's Pydantic schemas (Apache 2.0) to
match every other Chitti schema (MemoryRecord, EngagementSession,
LullabyRecord, ...). Pydantic isn't a Chitti dependency and wasn't
added just for this.

ReadingProfile is named to avoid colliding with parent_controls/
profiles.py's ChildProfile -- it's keyed by the same child_profile_id,
not a separate "learner" concept of its own.
"""
from dataclasses import dataclass, field
from datetime import datetime

from .curriculum import (
    GRAPHEME_INVENTORY,
    LEVEL_SEQUENCE,
    MASTERY_THRESHOLD,
    bkt_params_for_level,
)


@dataclass
class GraphemeMastery:
    """BKT knowledge state for a single grapheme -- the unit of mastery."""

    grapheme: str
    level: str
    p_mastery: float
    opportunities: int = 0
    correct: int = 0
    last_seen_session: int | None = None

    def is_mastered(self, threshold: float = MASTERY_THRESHOLD) -> bool:
        return self.p_mastery >= threshold


@dataclass
class ReadingProfile:
    """Per-child, cross-session reading state -- the mastery map plus
    personalization fields the book generator consumes."""

    child_profile_id: str
    interest: str = ""
    sight_words: list[str] = field(default_factory=list)
    masteries: dict[str, GraphemeMastery] = field(default_factory=dict)
    sessions_completed: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def new(
        cls, child_profile_id: str, *, interest: str = "", sight_words: list[str] | None = None
    ) -> "ReadingProfile":
        """Creates a fresh profile with every inventory grapheme at its BKT prior."""
        masteries = {
            grapheme: GraphemeMastery(
                grapheme=grapheme, level=level, p_mastery=bkt_params_for_level(level)["p_init"]
            )
            for grapheme, level in GRAPHEME_INVENTORY
        }
        return cls(
            child_profile_id=child_profile_id,
            interest=interest,
            sight_words=list(sight_words or []),
            masteries=masteries,
        )

    def is_level_mastered(self, level: str, threshold: float = MASTERY_THRESHOLD) -> bool:
        graphemes = [m for m in self.masteries.values() if m.level == level]
        return bool(graphemes) and all(m.is_mastered(threshold) for m in graphemes)

    def mastered_levels(self, threshold: float = MASTERY_THRESHOLD) -> list[str]:
        return [lvl for lvl in LEVEL_SEQUENCE if self.is_level_mastered(lvl, threshold)]


@dataclass
class Objective:
    """The next learning target chosen by the adaptive planner."""

    target_grapheme: str
    target_level: str
    mastered_levels: list[str] = field(default_factory=list)
    review_graphemes: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class GraphemeDelta:
    grapheme: str
    level: str
    p_before: float
    p_after: float
    n_correct: int
    n_incorrect: int

    @property
    def delta(self) -> float:
        return self.p_after - self.p_before


@dataclass
class MasteryDelta:
    changes: list[GraphemeDelta] = field(default_factory=list)
    newly_mastered: list[str] = field(default_factory=list)
    newly_mastered_levels: list[str] = field(default_factory=list)

    @property
    def graphemes_updated(self) -> list[str]:
        return [c.grapheme for c in self.changes]


@dataclass
class Miscue:
    """A single classified deviation between the expected text and the read-aloud."""

    kind: str  # correct | substitution | omission | insertion | self_correction | hesitation
    expected: str | None
    spoken: str | None
    position: int
    error_word: str | None = None


@dataclass
class AssessmentResult:
    """The deterministic miscue analysis of one read-aloud: errors +
    fluency + the evidence the BKT mastery model consumes."""

    expected_text: str
    spoken_text: str
    total_words: int
    words_correct: int
    errors: int
    substitutions: int = 0
    omissions: int = 0
    insertions: int = 0
    self_corrections: int = 0
    accuracy: float = 0.0
    wcpm: float = 0.0
    duration_seconds: float = 0.0
    miscues: list[Miscue] = field(default_factory=list)
    grapheme_evidence: dict[str, list[bool]] = field(default_factory=dict)
    # Decision 0055: the expected words actually read correctly, in
    # order (duplicates included) -- lets feedback.py cite a specific
    # real word from this read as evidence, instead of a list of
    # phonics sound labels disconnected from what the child actually did.
    correct_words: list[str] = field(default_factory=list)


@dataclass
class GeneratedBook:
    """An LLM-authored decodable practice book (decision 0051's
    book_generation.py). generation_source mirrors the original
    project's content-flywheel signal: "llm" (decodable + on-target),
    "llm_offtarget" (decodable but missed the target grapheme)."""

    title: str
    pages: list[str]
    target_grapheme: str
    objective: Objective
    sight_words: set[str] = field(default_factory=set)
    generation_source: str = "llm"

    @property
    def text(self) -> str:
        return " ".join(self.pages)

    @property
    def words(self) -> list[str]:
        return [w for page in self.pages for w in page.split()]
