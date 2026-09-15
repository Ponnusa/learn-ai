-- Migration 031: student course narratives
-- Applied automatically via main.py's lifespan() startup block — this file
-- documents the change, it is not run manually.
--
-- Cached AI narrative synthesizing all of a student's ladder session
-- reports across one whole course into a short teacher-facing paragraph.
-- One row per (student, course); regenerated only when report_count no
-- longer matches the current count of ready ladder_session_reports for
-- that pair (a new session resolved since it was last written).

CREATE TABLE IF NOT EXISTS student_course_narratives (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id    UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    narrative    TEXT NOT NULL,
    report_count INT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, course_id)
);
