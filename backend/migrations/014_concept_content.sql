-- Sprint 4: Teacher concept content (explanation text, images, syllabus PDF storage)

ALTER TABLE courses
  ADD COLUMN IF NOT EXISTS syllabus_pdf      BYTEA,
  ADD COLUMN IF NOT EXISTS syllabus_filename TEXT;

ALTER TABLE course_concepts
  ADD COLUMN IF NOT EXISTS content_text TEXT;

CREATE TABLE IF NOT EXISTS concept_images (
  id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  concept_id UUID         NOT NULL REFERENCES course_concepts(id) ON DELETE CASCADE,
  data       BYTEA        NOT NULL,
  mime_type  TEXT         NOT NULL DEFAULT 'image/jpeg',
  caption    TEXT,
  position   INT          NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ           DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_concept_images_concept
  ON concept_images(concept_id, position);
