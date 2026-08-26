-- Migration 026: 3-tier system for the developer API platform (admin-assigned)
-- Tier names are prefixed api_* deliberately -- the main app already has
-- tiers named 'free'/'learner'/'pro' in this same tier_config table, and
-- reusing those names here would silently share limits between two
-- unrelated products via get_limit(tier, feature).
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'api_free'
  CHECK (tier IN ('api_free', 'api_standard', 'api_enterprise'));

INSERT INTO tier_config (tier, feature, value_int, description)
SELECT * FROM (VALUES
    ('api_free',       'videos_daily',   2,  'Developer API free tier: videos per rolling 24h'),
    ('api_free',       'video_max_secs', 60, 'Developer API free tier: max video length'),
    ('api_standard',   'videos_daily',   10, 'Developer API standard tier: videos per rolling 24h'),
    ('api_standard',   'video_max_secs', 120,'Developer API standard tier: max video length'),
    ('api_enterprise', 'videos_daily',   -1, 'Developer API enterprise tier: unlimited'),
    ('api_enterprise', 'video_max_secs', 180,'Developer API enterprise tier: max video length')
) AS v(tier, feature, value_int, description)
WHERE NOT EXISTS (
    SELECT 1 FROM tier_config WHERE tier_config.tier = v.tier AND tier_config.feature = v.feature
);
