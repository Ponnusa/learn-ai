-- Migration 007: persist theme preference per user
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS theme TEXT DEFAULT 'dark'
    CHECK (theme IN ('dark', 'light'));
