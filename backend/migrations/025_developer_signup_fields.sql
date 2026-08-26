-- Migration 025: password-based developer signup (replaces magic-link for video-api app)
-- Splits api_keys.label into distinct company_name / description fields collected
-- at signup, instead of one free-text field collected later on the dashboard.
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS description TEXT;
UPDATE api_keys SET company_name = label WHERE company_name IS NULL AND label IS NOT NULL;
ALTER TABLE api_keys DROP COLUMN IF EXISTS label;
