-- Migration 004: conversation context for anti-repetition
-- Run once against the production DB.

ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS summary               TEXT,
  ADD COLUMN IF NOT EXISTS topics_covered        JSONB    DEFAULT '{"covered":[],"weak_areas":[]}'::jsonb,
  ADD COLUMN IF NOT EXISTS summarized_msg_count  INTEGER  DEFAULT 0;
