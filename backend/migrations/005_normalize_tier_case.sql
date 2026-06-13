-- Migration 005: normalize tier column to lowercase and add CHECK constraint
-- Fixes rows like tier='Pro' that don't match the lowercase tier_config keys.

UPDATE users SET tier = LOWER(tier) WHERE tier != LOWER(tier);

ALTER TABLE users
  ADD CONSTRAINT users_tier_lowercase
  CHECK (tier = LOWER(tier));
