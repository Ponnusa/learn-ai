-- Migration 023: expand language column to support Norwegian
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_language_check;
ALTER TABLE users ADD CONSTRAINT users_language_check
  CHECK (language IN ('en', 'fi', 'sv', 'es', 'fr', 'no'));
