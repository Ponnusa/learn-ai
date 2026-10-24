"""Reading Partner persistence (decision 0051). Two flat-row tables
(storage/migrations.py), matching every other domain repository here
(MemoryRepository, EngagementRepository, ...) rather than a JSON blob:
reading_profiles (one row per child) and reading_grapheme_mastery (one
row per child+grapheme). Scoped by child_profile_id throughout, same
as every other per-child repository.
"""
import sqlite3
from datetime import datetime, timezone

from companion_robot.storage.migrations import run_migrations

from .schema import GraphemeMastery, ReadingProfile

# Sight words are stored as a single delimited TEXT column rather than
# a second table or a JSON column -- the list is small and this keeps
# the schema flat like everywhere else in this project.
_SIGHT_WORD_SEP = "\x1f"


class ReadingRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def get_or_create(self, child_profile_id: str, *, interest: str = "") -> ReadingProfile:
        row = self._conn.execute(
            "SELECT * FROM reading_profiles WHERE child_profile_id = ?", (child_profile_id,)
        ).fetchone()
        if row is None:
            now = datetime.now(timezone.utc)
            profile = ReadingProfile.new(child_profile_id, interest=interest)
            profile.created_at = now
            profile.updated_at = now
            self.save(profile)
            return profile
        return self._load(child_profile_id, row)

    def _load(self, child_profile_id: str, row: sqlite3.Row) -> ReadingProfile:
        mastery_rows = self._conn.execute(
            "SELECT * FROM reading_grapheme_mastery WHERE child_profile_id = ?",
            (child_profile_id,),
        ).fetchall()
        masteries = {
            r["grapheme"]: GraphemeMastery(
                grapheme=r["grapheme"],
                level=r["level"],
                p_mastery=r["p_mastery"],
                opportunities=r["opportunities"],
                correct=r["correct"],
                last_seen_session=r["last_seen_session"],
            )
            for r in mastery_rows
        }
        sight_words = [w for w in row["sight_words"].split(_SIGHT_WORD_SEP) if w]
        completed_library_stories = [
            s for s in row["completed_library_stories"].split(_SIGHT_WORD_SEP) if s
        ]
        return ReadingProfile(
            child_profile_id=child_profile_id,
            interest=row["interest"],
            sight_words=sight_words,
            masteries=masteries,
            sessions_completed=row["sessions_completed"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            current_passage_key=row["current_passage_key"],
            current_sentence_index=row["current_sentence_index"],
            completed_library_stories=completed_library_stories,
        )

    def save(self, profile: ReadingProfile) -> None:
        """Upserts the profile row and every grapheme's mastery row.
        Called both to persist a brand-new profile and to persist the
        result of a session's BKT update."""
        now = datetime.now(timezone.utc)
        created_at = profile.created_at or now
        self._conn.execute(
            """
            INSERT INTO reading_profiles
                (child_profile_id, interest, sight_words, sessions_completed, created_at, updated_at,
                 current_passage_key, current_sentence_index, completed_library_stories)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(child_profile_id) DO UPDATE SET
                interest = excluded.interest,
                sight_words = excluded.sight_words,
                sessions_completed = excluded.sessions_completed,
                updated_at = excluded.updated_at,
                current_passage_key = excluded.current_passage_key,
                current_sentence_index = excluded.current_sentence_index,
                completed_library_stories = excluded.completed_library_stories
            """,
            (
                profile.child_profile_id,
                profile.interest,
                _SIGHT_WORD_SEP.join(profile.sight_words),
                profile.sessions_completed,
                created_at.isoformat(),
                now.isoformat(),
                profile.current_passage_key,
                profile.current_sentence_index,
                _SIGHT_WORD_SEP.join(profile.completed_library_stories),
            ),
        )
        for mastery in profile.masteries.values():
            self._conn.execute(
                """
                INSERT INTO reading_grapheme_mastery
                    (child_profile_id, grapheme, level, p_mastery, opportunities, correct, last_seen_session)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(child_profile_id, grapheme) DO UPDATE SET
                    level = excluded.level,
                    p_mastery = excluded.p_mastery,
                    opportunities = excluded.opportunities,
                    correct = excluded.correct,
                    last_seen_session = excluded.last_seen_session
                """,
                (
                    profile.child_profile_id,
                    mastery.grapheme,
                    mastery.level,
                    mastery.p_mastery,
                    mastery.opportunities,
                    mastery.correct,
                    mastery.last_seen_session,
                ),
            )
        self._conn.commit()
