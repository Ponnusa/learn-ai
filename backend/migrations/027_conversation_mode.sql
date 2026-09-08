-- Migration 027: conversation chat mode (direct | exploratory)
-- Applied automatically via main.py's lifespan() startup block — this file
-- documents the change, it is not run manually.

ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'direct';
