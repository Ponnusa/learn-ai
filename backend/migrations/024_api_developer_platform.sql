-- Migration 024: API developer platform (video-api app)
-- New table for third-party API keys, plus tracking columns on videos so
-- API-generated videos are distinguishable from the main app's own videos.

CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash     TEXT NOT NULL UNIQUE,
    label        TEXT,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'revoked')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at  TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status);

ALTER TABLE videos ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'app';
ALTER TABLE videos ADD COLUMN IF NOT EXISTS api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_videos_api_key ON videos(api_key_id) WHERE api_key_id IS NOT NULL;

-- Hard cap: 1 video per api_partner account, lifetime (not daily like other
-- tiers) -- enforced in code against this config row so it's adjustable via
-- SQL later without a redeploy, matching the existing tier_config pattern.
INSERT INTO tier_config (tier, feature, value_int, description)
SELECT 'api_partner', 'videos_lifetime', 1, 'Hard lifetime cap on videos generated via the developer API (beta)'
WHERE NOT EXISTS (
    SELECT 1 FROM tier_config WHERE tier = 'api_partner' AND feature = 'videos_lifetime'
);
