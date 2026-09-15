-- Migration 030: ladder session reports
-- Applied automatically via main.py's lifespan() startup block — this file
-- documents the change, it is not run manually.
--
-- One row per resolved guided-discovery (ladder) chain, holding the
-- AI-generated rubric-scored outcome report a teacher can view: academic
-- understanding, thinking-radar dimensions (decision-making, justification,
-- constraint awareness, transfer), strengths/growth, suggested next topic.
-- Generated asynchronously by services.ladder_report as a background task
-- right after the chain resolves — never blocks the student's own reply.

CREATE TABLE IF NOT EXISTS ladder_session_reports (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guided_discovery_event_id  UUID NOT NULL REFERENCES guided_discovery_events(id) ON DELETE CASCADE,
    conversation_id            UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    student_id                 UUID REFERENCES users(id) ON DELETE CASCADE,
    concept_id                 UUID REFERENCES course_concepts(id) ON DELETE CASCADE,
    topic                      TEXT,
    status                     TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','ready','failed')),
    report                     JSONB,
    error_message              TEXT,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ladder_session_reports_event ON ladder_session_reports(guided_discovery_event_id);
CREATE INDEX IF NOT EXISTS idx_ladder_session_reports_student_concept ON ladder_session_reports(student_id, concept_id);
