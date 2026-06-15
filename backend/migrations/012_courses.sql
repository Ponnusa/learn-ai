-- ============================================================
-- Sprint 2: Course builder
-- ============================================================

CREATE TABLE courses (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  description TEXT,
  subject     TEXT,
  grade       TEXT,
  status      TEXT NOT NULL DEFAULT 'draft',   -- draft | published
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE course_units (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id   UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  title       TEXT NOT NULL,
  description TEXT,
  position    INT  NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE course_concepts (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  unit_id      UUID NOT NULL REFERENCES course_units(id) ON DELETE CASCADE,
  title        TEXT NOT NULL,
  description  TEXT,
  study_set_id UUID REFERENCES study_sets(id) ON DELETE SET NULL,
  position     INT  NOT NULL DEFAULT 0,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Assign a course to one or more classrooms
CREATE TABLE classroom_courses (
  classroom_id UUID REFERENCES classrooms(id) ON DELETE CASCADE,
  course_id    UUID REFERENCES courses(id)    ON DELETE CASCADE,
  assigned_at  TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (classroom_id, course_id)
);

CREATE INDEX idx_courses_teacher          ON courses(teacher_id);
CREATE INDEX idx_course_units_course      ON course_units(course_id, position);
CREATE INDEX idx_course_concepts_unit     ON course_concepts(unit_id, position);
CREATE INDEX idx_classroom_courses_course ON classroom_courses(course_id);
