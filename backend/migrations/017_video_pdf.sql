-- Fix: store chapter PDF bytes so teacher can view it in the concept editor
ALTER TABLE course_chapters
  ADD COLUMN IF NOT EXISTS pdf_data BYTEA;

-- AI-generated concept video (MP4 from TTS audio + title slide via ffmpeg)
ALTER TABLE course_concepts
  ADD COLUMN IF NOT EXISTS video_data   BYTEA,
  ADD COLUMN IF NOT EXISTS video_status TEXT NOT NULL DEFAULT 'none';

CREATE INDEX IF NOT EXISTS idx_concept_video ON course_concepts(video_status);
