-- ============================================================
-- Learn-AI  —  Initial Schema
-- Run once against your Neon PostgreSQL database
-- ============================================================

-- ── Extensions ──────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- IDENTITY
-- ============================================================

CREATE TABLE anonymous_sessions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  ip_hash         TEXT,
  user_agent_hash TEXT,
  converted_to    UUID,                        -- set on signup → users.id
  -- usage counters (lifetime for anonymous)
  msg_count       INT DEFAULT 0,
  video_count     INT DEFAULT 0,
  quiz_count      INT DEFAULT 0,
  upload_count    INT DEFAULT 0,
  -- lightweight session profiling
  session_profile JSONB DEFAULT '{}'
);

CREATE TABLE users (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email              TEXT UNIQUE NOT NULL,
  name               TEXT,
  avatar_url         TEXT,
  tier               TEXT DEFAULT 'free',         -- free | learner | pro
  knowledge_level    TEXT DEFAULT 'intermediate',  -- beginner | intermediate | advanced
  language           TEXT DEFAULT 'en',
  stripe_customer_id TEXT,
  created_at         TIMESTAMPTZ DEFAULT NOW(),
  last_seen_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Magic-link tokens
CREATE TABLE auth_tokens (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
  token      TEXT UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at    TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SUBSCRIPTIONS
-- ============================================================

CREATE TABLE subscriptions (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID REFERENCES users(id) ON DELETE CASCADE,
  tier                 TEXT NOT NULL,
  status               TEXT NOT NULL DEFAULT 'active', -- active | cancelled | past_due
  stripe_sub_id        TEXT UNIQUE,
  current_period_start TIMESTAMPTZ,
  current_period_end   TIMESTAMPTZ,
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TIER CONFIG  (edit rows to change limits — no deploy needed)
-- ============================================================

CREATE TABLE tier_config (
  id          SERIAL PRIMARY KEY,
  tier        TEXT NOT NULL,
  feature     TEXT NOT NULL,
  value_int   INT,
  value_text  TEXT,
  value_bool  BOOLEAN,
  description TEXT,
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tier, feature)
);

INSERT INTO tier_config (tier, feature, value_int, description) VALUES
  -- ANONYMOUS
  ('anonymous','messages_total',       8,   'Lifetime messages per session'),
  ('anonymous','videos_total',         1,   'Lifetime videos per session'),
  ('anonymous','video_max_secs',       60,  'Max video duration seconds'),
  ('anonymous','quiz_total',           1,   'Lifetime quizzes per session'),
  ('anonymous','quiz_questions_max',   3,   'Questions per quiz'),
  ('anonymous','pdf_pages_max',        1,   'Max PDF pages analyzed'),
  ('anonymous','topics_total',         1,   'Topics before signup gate'),
  ('anonymous','image_uploads_total',  2,   'Image uploads per session'),
  ('anonymous','study_sets_max',       0,   '0 = not available'),
  ('anonymous','history_days',         0,   '0 = localStorage only'),
  -- FREE
  ('free','messages_daily',           25,   'Chat messages per day'),
  ('free','videos_daily',              3,   'Videos per day'),
  ('free','video_max_secs',           60,   'Max video duration seconds'),
  ('free','quiz_daily',                5,   'Quizzes per day'),
  ('free','quiz_questions_max',        5,   'Questions per quiz'),
  ('free','pdf_pages_max',             5,   'Max PDF pages per upload'),
  ('free','topics_daily',              5,   'Topics per day'),
  ('free','image_uploads_daily',       5,   'Image uploads per day'),
  ('free','study_sets_max',            2,   'Max active study sets'),
  ('free','history_days',              7,   'Conversation history days'),
  -- LEARNER
  ('learner','messages_daily',       100,   'Chat messages per day'),
  ('learner','videos_daily',           5,   'Videos per day'),
  ('learner','video_max_secs',       180,   'Max video duration seconds'),
  ('learner','quiz_daily',            -1,   'Unlimited'),
  ('learner','quiz_questions_max',    10,   'Questions per quiz'),
  ('learner','pdf_pages_max',         20,   'Max PDF pages per upload'),
  ('learner','topics_daily',          20,   'Topics per day'),
  ('learner','image_uploads_daily',   -1,   'Unlimited'),
  ('learner','study_sets_max',        10,   'Max active study sets'),
  ('learner','history_days',          30,   'Conversation history days'),
  -- PRO
  ('pro','messages_daily',            -1,   'Unlimited'),
  ('pro','videos_daily',              10,   'Videos per day'),
  ('pro','video_max_secs',           300,   'Max video duration seconds'),
  ('pro','quiz_daily',                -1,   'Unlimited'),
  ('pro','quiz_questions_max',        15,   'Questions per quiz'),
  ('pro','pdf_pages_max',            100,   'Full PDFs'),
  ('pro','topics_daily',              -1,   'Unlimited'),
  ('pro','image_uploads_daily',       -1,   'Unlimited'),
  ('pro','study_sets_max',            -1,   'Unlimited'),
  ('pro','history_days',              -1,   'Forever');

-- ============================================================
-- FEATURE FLAGS  (toggle features per subject — no deploy needed)
-- ============================================================

CREATE TABLE feature_flags (
  id         SERIAL PRIMARY KEY,
  feature    TEXT NOT NULL,
  subject    TEXT,
  enabled    BOOLEAN DEFAULT FALSE,
  note       TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(feature, subject)
);

INSERT INTO feature_flags (feature, subject, enabled, note) VALUES
  ('video_generation','Mathematics',            TRUE,  'Full Manim — equations, graphs, proofs'),
  ('video_generation','Physics',                TRUE,  'Full Manim — mechanics, waves, forces'),
  ('video_generation','Chemistry',              TRUE,  'Full Manim — reactions, molecular, equations'),
  ('video_generation','Computer Science',       FALSE, 'Planned — sorting algos, data structures'),
  ('video_generation','Biology',                FALSE, 'Planned — cell diagrams, DNA'),
  ('video_generation','Engineering',            FALSE, 'Planned — circuits, mechanics'),
  ('video_generation','Economics',              FALSE, 'Planned — supply/demand curves'),
  ('video_generation','History',                FALSE, 'Not planned'),
  ('video_generation','Geography',              FALSE, 'Not planned'),
  ('video_generation','Literature',             FALSE, 'Not planned'),
  ('video_generation','Language & Linguistics', FALSE, 'Not planned'),
  ('video_generation','Philosophy',             FALSE, 'Not planned'),
  ('video_generation','Psychology',             FALSE, 'Planned — neural diagrams'),
  ('video_generation','Medicine & Health',      FALSE, 'Planned — anatomy'),
  ('video_generation','Business',               FALSE, 'Planned — charts, flows'),
  ('video_generation','Art & Design',           FALSE, 'Not planned'),
  ('video_generation','Music',                  FALSE, 'Planned — wave physics'),
  ('video_generation','Law',                    FALSE, 'Not planned'),
  ('video_generation','Environmental Science',  FALSE, 'Planned'),
  ('video_generation','Other',                  FALSE, 'Unknown subject');

-- ============================================================
-- CONVERSATIONS & MESSAGES
-- ============================================================

CREATE TABLE conversations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
  session_id      UUID REFERENCES anonymous_sessions(id) ON DELETE CASCADE,
  title           TEXT,
  subject         TEXT,
  subtopic        TEXT,
  subject_confidence FLOAT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_conv_user     ON conversations(user_id);
CREATE INDEX idx_conv_subject  ON conversations(subject);
CREATE INDEX idx_conv_updated  ON conversations(updated_at DESC);

CREATE TABLE messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL,   -- user | assistant
  content         TEXT NOT NULL,
  content_type    TEXT DEFAULT 'text',  -- text | image_url | pdf_ref
  metadata        JSONB DEFAULT '{}',   -- suggestion_chips, actions, subject etc.
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_msg_conv ON messages(conversation_id, created_at);

-- ============================================================
-- VIDEOS  (same schema as AnimLearn — same Cloud Run reads/writes)
-- ============================================================

CREATE TABLE videos (
  id                  SERIAL PRIMARY KEY,
  user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
  session_id          UUID REFERENCES anonymous_sessions(id) ON DELETE SET NULL,
  conversation_id     UUID REFERENCES conversations(id) ON DELETE SET NULL,
  message_id          UUID REFERENCES messages(id) ON DELETE SET NULL,
  -- AnimLearn pipeline fields (Cloud Run reads/writes these)
  generated_code      TEXT,
  scene_name          TEXT DEFAULT 'MainScene',
  svg_urls            JSONB DEFAULT '{}',
  transcript_markdown TEXT,
  verified_solution   TEXT,
  -- status & output
  status              TEXT DEFAULT 'pending', -- pending|queued|rendering|done|failed
  video_url           TEXT,
  thumbnail_url       TEXT,
  error_message       TEXT,
  -- metadata
  prompt              TEXT,
  duration_secs       INT,
  max_duration        INT DEFAULT 60,
  aspect_ratio        TEXT DEFAULT '16:9',
  language            TEXT DEFAULT 'en',
  subject             TEXT,
  is_public           BOOLEAN DEFAULT FALSE,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_videos_user   ON videos(user_id);
CREATE INDEX idx_videos_status ON videos(status);

-- ============================================================
-- QUIZZES
-- ============================================================

CREATE TABLE quizzes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
  user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
  session_id      UUID REFERENCES anonymous_sessions(id) ON DELETE SET NULL,
  subject         TEXT,
  questions       JSONB NOT NULL,   -- [{q, options, correct, explanation, difficulty}]
  user_answers    JSONB,
  score           INT,
  max_score       INT,
  completed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- UPLOADS
-- ============================================================

CREATE TABLE uploads (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID REFERENCES users(id) ON DELETE SET NULL,
  session_id       UUID REFERENCES anonymous_sessions(id) ON DELETE SET NULL,
  conversation_id  UUID REFERENCES conversations(id) ON DELETE SET NULL,
  file_type        TEXT,            -- pdf | image
  file_url         TEXT,
  original_name    TEXT,
  page_count       INT,
  pages_used       INT,
  extracted_text   TEXT,
  ocr_text         TEXT,
  detected_subject TEXT,
  detected_subtopic TEXT,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- STUDY SETS
-- ============================================================

CREATE TABLE study_sets (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  title       TEXT NOT NULL,
  subject     TEXT,
  source_type TEXT,   -- pdf | image | topic | conversation
  source_id   UUID,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE study_concepts (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  study_set_id   UUID REFERENCES study_sets(id) ON DELETE CASCADE,
  title          TEXT NOT NULL,
  explanation    TEXT,
  video_id       INT REFERENCES videos(id) ON DELETE SET NULL,
  order_index    INT DEFAULT 0,
  mastery_level  INT DEFAULT 0,     -- 0-5 spaced repetition
  next_review_at TIMESTAMPTZ,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- STUDENT PROFILES  (adaptive AI personalization)
-- ============================================================

CREATE TABLE student_profiles (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
  -- Skill scores per subject  e.g. {"Physics": 62, "Mathematics": 81}
  skill_scores          JSONB DEFAULT '{}',
  -- AI-written, AI-updated prompt modifier (2-4 sentences)
  prompt_modifier       TEXT DEFAULT '',
  -- Learning characteristics
  learning_style        TEXT DEFAULT 'balanced',    -- visual|textual|example_first|theory_first|balanced
  vocab_level           TEXT DEFAULT 'intermediate',-- simple|intermediate|technical
  explanation_depth     TEXT DEFAULT 'moderate',    -- brief|moderate|detailed
  -- History
  known_misconceptions  JSONB DEFAULT '[]',
  mastered_concepts     JSONB DEFAULT '[]',
  struggle_areas        JSONB DEFAULT '[]',
  preferred_analogies   JSONB DEFAULT '[]',         -- ["sports","cooking"]
  -- Engagement counters
  total_messages        INT DEFAULT 0,
  total_quizzes         INT DEFAULT 0,
  total_videos          INT DEFAULT 0,
  avg_quiz_score        FLOAT DEFAULT 0,
  simplify_requests     INT DEFAULT 0,
  deeper_requests       INT DEFAULT 0,
  -- Meta
  profile_version       INT DEFAULT 1,
  last_updated          TIMESTAMPTZ DEFAULT NOW(),
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE skill_score_history (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  subject     TEXT NOT NULL,
  score       INT NOT NULL,
  delta       INT NOT NULL,
  reason      TEXT,   -- quiz_completed | session_analysis | self_reported
  recorded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_score_history_user ON skill_score_history(user_id, subject);

-- ============================================================
-- USAGE EVENTS  (credit enforcement + analytics)
-- ============================================================

CREATE TABLE usage_events (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
  session_id  UUID REFERENCES anonymous_sessions(id) ON DELETE SET NULL,
  event_type  TEXT NOT NULL,  -- message_sent|video_generated|quiz_taken|pdf_uploaded
  subject     TEXT,
  metadata    JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_usage_user_date ON usage_events(user_id, created_at DESC);
CREATE INDEX idx_usage_sess_date ON usage_events(session_id, created_at DESC);

-- Daily usage view for credit checking
CREATE VIEW daily_usage AS
SELECT
  COALESCE(user_id::TEXT, session_id::TEXT) AS identity_key,
  event_type,
  COUNT(*) AS cnt,
  DATE(created_at AT TIME ZONE 'UTC') AS day
FROM usage_events
GROUP BY 1, 2, 4;
