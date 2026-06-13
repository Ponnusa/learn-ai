-- Migration 006: Add grade, goal, subject_confidence to student_profiles
ALTER TABLE student_profiles
  ADD COLUMN IF NOT EXISTS grade              TEXT,
  ADD COLUMN IF NOT EXISTS goal               TEXT,
  ADD COLUMN IF NOT EXISTS subject_confidence JSONB DEFAULT '{}'::jsonb;
