-- Multi-modal lesson video pipeline (Manim + Nano Banana image + Veo video
-- segments per lesson, composited into one mp4). Purely additive: no changes
-- to the existing `videos` table. A `videos` row with no video_segments rows
-- renders exactly as it does today (single Manim scene) — the worker
-- dispatches by presence of segment rows, not by a flag column.

CREATE TABLE IF NOT EXISTS video_segments (
  id                          SERIAL PRIMARY KEY,
  video_id                    INT  NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  segment_id                  TEXT NOT NULL,      -- storyboard-scoped id, e.g. "seg-0"
  segment_order               INT  NOT NULL,      -- render/composite order within this video
  type                        TEXT NOT NULL CHECK (type IN ('manim', 'image', 'video')),
  target_duration_seconds     REAL,
  actual_duration_seconds     REAL,
  subject_area                TEXT,
  aspect_ratio                TEXT DEFAULT '16:9',
  narration_text              TEXT,
  generation_prompt           TEXT,
  style_reference_segment_id  TEXT,               -- references another row's segment_id, same video
  source_asset_url            TEXT,               -- still image / SVG, whatever QA validated
  clip_url                    TEXT,               -- final per-segment mp4 fed to the compositor
  generated_code              TEXT,               -- manim segments only
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

-- Cross-lesson asset cache (extends the existing per-request-only SVG cache
-- pattern into something persisted). Stores the R2 key, never a presigned
-- URL — those expire, so a fresh one is minted on read at lookup time.
CREATE TABLE IF NOT EXISTS generated_assets (
  prompt_hash  TEXT PRIMARY KEY,
  asset_type   TEXT NOT NULL,   -- image | image_clip | video_clip | held_frame_clip
  r2_key       TEXT NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);
