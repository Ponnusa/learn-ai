-- Migration 022: add suggested_prompts to course_concepts
-- Stores AI-generated teacher prompt suggestions per concept.
-- Generated during pipeline; shown as clickable chips in teacher studio.

ALTER TABLE course_concepts
  ADD COLUMN IF NOT EXISTS suggested_prompts JSONB DEFAULT '[]';
