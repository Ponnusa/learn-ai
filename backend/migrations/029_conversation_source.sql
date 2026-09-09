-- Migration 029: conversation origin tagging (app | extension | ...)
-- Applied automatically via main.py's lifespan() startup block — this file
-- documents the change, it is not run manually.
--
-- Mirrors the existing videos.source column (migration 024) — lets us tell
-- app-originated conversations apart from ones started elsewhere (e.g. the
-- Chrome extension), for funnel/analytics purposes.

ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'app';
