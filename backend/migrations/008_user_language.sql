-- Migration 008: persist language preference per user
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en'
    CHECK (language IN ('en', 'fi', 'sv'));
