-- ============================================================
-- Sprint 1: Classrooms + student enrollment
-- ============================================================

CREATE TABLE classrooms (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  institution_id UUID REFERENCES institutions(id)   ON DELETE SET NULL,
  name           TEXT NOT NULL,
  subject        TEXT,
  grade          TEXT,
  join_code      TEXT UNIQUE NOT NULL
                   DEFAULT upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 6)),
  is_active      BOOLEAN NOT NULL DEFAULT true,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE classroom_students (
  classroom_id UUID REFERENCES classrooms(id) ON DELETE CASCADE,
  student_id   UUID REFERENCES users(id)      ON DELETE CASCADE,
  joined_at    TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (classroom_id, student_id)
);

CREATE INDEX idx_classrooms_teacher          ON classrooms(teacher_id);
CREATE INDEX idx_classrooms_join_code        ON classrooms(join_code);
CREATE INDEX idx_classroom_students_student  ON classroom_students(student_id);
CREATE INDEX idx_classroom_students_class    ON classroom_students(classroom_id);
