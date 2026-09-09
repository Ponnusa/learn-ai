-- Migration 028: guided-discovery (ladder) resolution events
-- Applied automatically via main.py's lifespan() startup block — this file
-- documents the change, it is not run manually.
--
-- One row per guided-discovery chain that resolves, recording how many
-- scaffolding steps (WAITING:1 turns) it took to reach the answer.

CREATE TABLE IF NOT EXISTS guided_discovery_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    message_id      UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    steps           INT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guided_discovery_events_conv ON guided_discovery_events(conversation_id);
CREATE INDEX IF NOT EXISTS idx_guided_discovery_events_user ON guided_discovery_events(user_id);
