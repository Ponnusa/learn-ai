-- Sprint 6: AI asset generation per concept (quiz, flashcards, audio)

ALTER TABLE course_concepts
  ADD COLUMN IF NOT EXISTS quiz_status       TEXT NOT NULL DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS flashcard_status  TEXT NOT NULL DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS audio_status      TEXT NOT NULL DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS audio_data        BYTEA,
  ADD COLUMN IF NOT EXISTS audio_duration_sec INT;

CREATE TABLE IF NOT EXISTS concept_quiz_questions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  concept_id  UUID NOT NULL REFERENCES course_concepts(id) ON DELETE CASCADE,
  question    TEXT NOT NULL,
  options     JSONB NOT NULL,   -- ["option A", "option B", "option C", "option D"]
  correct_idx INT  NOT NULL,    -- 0-based index into options
  explanation TEXT,
  position    INT  NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS concept_flashcards (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  concept_id  UUID NOT NULL REFERENCES course_concepts(id) ON DELETE CASCADE,
  front       TEXT NOT NULL,
  back        TEXT NOT NULL,
  position    INT  NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiz_concept        ON concept_quiz_questions(concept_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_concept  ON concept_flashcards(concept_id);
CREATE INDEX IF NOT EXISTS idx_concept_audio       ON course_concepts(audio_status);
