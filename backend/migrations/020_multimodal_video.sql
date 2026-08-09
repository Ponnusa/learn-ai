-- Multi-modal storyboard video pipeline opt-in.
--
-- Adds the per-user flag that lets the GCP worker choose between the
-- existing single-shot Manim path and the new storyboard-based pipeline
-- (Manim + Nano Banana image segments, composited into one mp4).
--
-- Also idempotently re-creates the two segment tables from 019_video_segments.sql
-- in case that migration was never applied to this environment.

-- ── Segment pipeline tables (idempotent — safe if 019 was already applied) ──

CREATE TABLE IF NOT EXISTS video_segments (
  id                          SERIAL PRIMARY KEY,
  video_id                    INT  NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  segment_id                  TEXT NOT NULL,
  segment_order               INT  NOT NULL,
  type                        TEXT NOT NULL CHECK (type IN ('manim', 'image', 'video')),
  target_duration_seconds     REAL,
  actual_duration_seconds     REAL,
  subject_area                TEXT,
  aspect_ratio                TEXT DEFAULT '16:9',
  narration_text              TEXT,
  generation_prompt           TEXT,
  style_reference_segment_id  TEXT,
  source_asset_url            TEXT,
  clip_url                    TEXT,
  generated_code              TEXT,
  status                      TEXT NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'generating', 'rendered', 'failed')),
  retry_count                 INT  NOT NULL DEFAULT 0,
  error_message               TEXT,
  prompt_hash                 TEXT,
  created_at                  TIMESTAMPTZ DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (video_id, segment_id)
);

CREATE INDEX IF NOT EXISTS idx_video_segments_video_id ON video_segments(video_id);

CREATE TABLE IF NOT EXISTS generated_assets (
  prompt_hash  TEXT PRIMARY KEY,
  asset_type   TEXT NOT NULL,
  r2_key       TEXT NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Per-user opt-in flag ─────────────────────────────────────────────────────

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS multimodal_video_enabled BOOLEAN NOT NULL DEFAULT FALSE;
