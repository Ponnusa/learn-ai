-- ============================================================
-- Sprint: TEKS-aligned curriculum contexts
-- Completely isolated from existing course builder.
-- courses without a curriculum_context_id are unaffected.
-- ============================================================

CREATE TABLE curriculum_contexts (
  id                UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  name              TEXT    NOT NULL,             -- "6th Grade Science - Thermal Energy (Unit 1)"
  driving_question  TEXT,                         -- unit driving question shown in chat banner
  teks_codes        TEXT[]  DEFAULT '{}',         -- ['6.6A','6.6B','6.6C','6.6D','6.8B']
  grade_level       TEXT,                         -- "6th Grade"
  subject           TEXT,                         -- "Science"
  active_lesson     INT     DEFAULT 1,            -- which lesson class is currently on (teacher updates)
  lesson_count      INT     DEFAULT 1,            -- total lessons in the unit
  key_ideas         JSONB   DEFAULT '[]',         -- what students should figure out (AI guides toward, never states)
  vocabulary        TEXT[]  DEFAULT '{}',         -- unit key terms
  inquiry_guardrail TEXT,                         -- pedagogy instruction for AI
  unit_start_date   DATE,
  unit_end_date     DATE,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Nullable FK on courses — existing rows get NULL, zero impact
ALTER TABLE courses
  ADD COLUMN curriculum_context_id UUID
  REFERENCES curriculum_contexts(id) ON DELETE SET NULL;

CREATE INDEX idx_courses_curriculum ON courses(curriculum_context_id);
