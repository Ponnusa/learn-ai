-- Sprint 5: AI concept pipeline (chapter upload → extract → summarize → approve)

ALTER TABLE course_concepts
  ADD COLUMN IF NOT EXISTS source_text     TEXT,        -- verbatim chunk AI grounded on
  ADD COLUMN IF NOT EXISTS ai_summary      TEXT,        -- AI-generated student explanation
  ADD COLUMN IF NOT EXISTS ai_transcript   TEXT,        -- video narration script
  ADD COLUMN IF NOT EXISTS pipeline_status TEXT NOT NULL DEFAULT 'draft',
  -- draft | summarizing | ready | approved | failed
  ADD COLUMN IF NOT EXISTS approved_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS chapter_ref     TEXT;        -- FK to course_chapters.id (text)

-- Track chapter uploads per course
CREATE TABLE IF NOT EXISTS course_chapters (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id     UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  filename      TEXT NOT NULL,
  page_count    INT,
  concept_count INT,
  status        TEXT NOT NULL DEFAULT 'processing',  -- processing | ready | failed
  error_msg     TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_course_chapters_course
  ON course_chapters(course_id);
CREATE INDEX IF NOT EXISTS idx_concept_pipeline
  ON course_concepts(pipeline_status);
