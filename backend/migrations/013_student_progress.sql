-- ============================================================
-- Sprint 3: Student concept progress tracking
-- ============================================================

CREATE TABLE student_concept_progress (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id    UUID NOT NULL REFERENCES users(id)            ON DELETE CASCADE,
  concept_id    UUID NOT NULL REFERENCES course_concepts(id)  ON DELETE CASCADE,
  course_id     UUID NOT NULL REFERENCES courses(id)          ON DELETE CASCADE,
  visited       BOOLEAN     NOT NULL DEFAULT false,
  visited_at    TIMESTAMPTZ,
  quiz_score    FLOAT,
  quiz_taken_at TIMESTAMPTZ,
  last_seen_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (student_id, concept_id)
);

CREATE INDEX idx_scp_student        ON student_concept_progress(student_id);
CREATE INDEX idx_scp_student_course ON student_concept_progress(student_id, course_id);
