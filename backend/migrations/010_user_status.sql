-- ============================================================
-- Sprint 0 patch: user active/disabled flag
-- ============================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;

-- Block disabled users at query time
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active) WHERE is_active = false;
