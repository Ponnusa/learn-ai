"""
Learn-AI Backend — FastAPI
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_pool, close_pool
from config import settings
from routers import auth, sessions, chat, videos, quizzes, uploads, studysets, images
from routers import teacher_auth, institutions, admin, classrooms, courses, students, messages, assignments


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    # Auto-migrate new columns (safe to run on every startup)
    import logging
    _log = logging.getLogger("startup")
    from database import get_db
    async with get_db() as db:
        for sql in [
            # ── existing columns ─────────────────────────────────────────────
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT",
            # ── StudySet conversation link ────────────────────────────────────
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS study_set_id UUID REFERENCES study_sets(id) ON DELETE SET NULL",
            # ── StudySets: patch old stub schema from 001_initial.sql ────────
            # study_sets — add columns missing from the 001 stub
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS session_id  UUID",
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS summary     TEXT",
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS status      TEXT NOT NULL DEFAULT 'empty'",
            "ALTER TABLE study_sets ADD COLUMN IF NOT EXISTS updated_at  TIMESTAMPTZ DEFAULT NOW()",
            # study_concepts — old stub used 'title' instead of 'name'
            "ALTER TABLE study_concepts ADD COLUMN IF NOT EXISTS name        TEXT",
            "ALTER TABLE study_concepts ADD COLUMN IF NOT EXISTS definition  TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE study_concepts ADD COLUMN IF NOT EXISTS order_index INT NOT NULL DEFAULT 0",
            # ── Educational Images ────────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS educational_images (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
                session_id   UUID REFERENCES anonymous_sessions(id) ON DELETE SET NULL,
                concept      TEXT NOT NULL,
                domain       TEXT,
                spec         JSONB DEFAULT '{}',
                prompt       TEXT,
                image_url    TEXT,
                status       TEXT NOT NULL DEFAULT 'processing',
                error_msg    TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_edu_img_user ON educational_images(user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_edu_img_sess ON educational_images(session_id, created_at DESC)",
            # ── Educational Images: conversation/study-set linking ────────────
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL",
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS study_set_id    UUID REFERENCES study_sets(id) ON DELETE SET NULL",
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS message_id      TEXT",
            "CREATE INDEX IF NOT EXISTS idx_edu_img_conv ON educational_images(conversation_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_edu_img_ss   ON educational_images(study_set_id, created_at DESC)",
            # ── Educational Images: Knowledge-Layer columns ───────────────────
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS knowledge_model     JSONB DEFAULT '{}'",
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS diagram_plan        JSONB DEFAULT '{}'",
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS critic_report       JSONB DEFAULT '{}'",
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS diagram_type        TEXT",
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS generation_attempts INT  DEFAULT 1",
            "ALTER TABLE educational_images ADD COLUMN IF NOT EXISTS description         TEXT",
            "ALTER TABLE anonymous_sessions ADD COLUMN IF NOT EXISTS image_count INT DEFAULT 0",
            # ── Ensure images_daily is in tier_config (upsert so re-runs are safe) ─
            "INSERT INTO tier_config (tier, feature, value_int, description) VALUES ('anonymous','images_total',1,'Lifetime images per session') ON CONFLICT (tier,feature) DO NOTHING",
            "INSERT INTO tier_config (tier, feature, value_int, description) VALUES ('free','images_daily',3,'Images per day') ON CONFLICT (tier,feature) DO NOTHING",
            "INSERT INTO tier_config (tier, feature, value_int, description) VALUES ('learner','images_daily',10,'Images per day') ON CONFLICT (tier,feature) DO NOTHING",
            "INSERT INTO tier_config (tier, feature, value_int, description) VALUES ('pro','images_daily',-1,'Unlimited') ON CONFLICT (tier,feature) DO NOTHING",
            # ── StudySets: create new tables that didn't exist in 001 ─────────
            """
            CREATE TABLE IF NOT EXISTS study_materials (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                study_set_id UUID NOT NULL REFERENCES study_sets(id) ON DELETE CASCADE,
                filename     TEXT NOT NULL DEFAULT 'upload.pdf',
                file_url     TEXT,
                raw_text     TEXT,
                page_count   INT,
                char_count   INT,
                status       TEXT NOT NULL DEFAULT 'pending',
                error_msg    TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS study_flashcards (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                study_set_id UUID NOT NULL REFERENCES study_sets(id) ON DELETE CASCADE,
                concept_id   UUID REFERENCES study_concepts(id) ON DELETE SET NULL,
                front        TEXT NOT NULL,
                back         TEXT NOT NULL,
                order_index  INT NOT NULL DEFAULT 0,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS study_card_reviews (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                flashcard_id UUID NOT NULL REFERENCES study_flashcards(id) ON DELETE CASCADE,
                rating       INT NOT NULL,
                reviewed_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            # ── Sprint 0: institutions / teacher accounts / invites (009) ─────
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS account_type TEXT NOT NULL DEFAULT 'student'",
            """
            CREATE TABLE IF NOT EXISTS institutions (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name         TEXT NOT NULL,
                type         TEXT NOT NULL,
                email_domain TEXT,
                country      TEXT,
                plan         TEXT NOT NULL DEFAULT 'trial',
                max_teachers INT  NOT NULL DEFAULT 5,
                max_students INT  NOT NULL DEFAULT 50,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS institution_members (
                institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
                user_id        UUID REFERENCES users(id)        ON DELETE CASCADE,
                role           TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'active',
                invited_by     UUID REFERENCES users(id),
                joined_at      TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (institution_id, user_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_institution_members_user ON institution_members(user_id)",
            """
            CREATE TABLE IF NOT EXISTS teacher_invites (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                code       TEXT UNIQUE NOT NULL DEFAULT upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8)),
                email      TEXT,
                note       TEXT,
                created_by UUID REFERENCES users(id),
                used_by    UUID REFERENCES users(id),
                used_at    TIMESTAMPTZ,
                expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS teacher_applications (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                type         TEXT NOT NULL,
                name         TEXT NOT NULL,
                email        TEXT NOT NULL,
                school_name  TEXT,
                subject      TEXT,
                message      TEXT,
                inst_type    TEXT,
                country      TEXT,
                est_teachers INT,
                est_students INT,
                email_domain TEXT,
                status       TEXT NOT NULL DEFAULT 'pending',
                reviewed_by  UUID REFERENCES users(id),
                reviewed_at  TIMESTAMPTZ,
                reject_reason TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_teacher_applications_status ON teacher_applications(status)",
            "CREATE INDEX IF NOT EXISTS idx_teacher_applications_email  ON teacher_applications(email)",
            # ── Sprint 0 patch: user active flag (010) ─────────────────────────
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
            "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active) WHERE is_active = false",
            # ── Sprint 1: classrooms (011) ──────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS classrooms (
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
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS classroom_students (
                classroom_id UUID REFERENCES classrooms(id) ON DELETE CASCADE,
                student_id   UUID REFERENCES users(id)      ON DELETE CASCADE,
                joined_at    TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (classroom_id, student_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_classrooms_teacher          ON classrooms(teacher_id)",
            "CREATE INDEX IF NOT EXISTS idx_classrooms_join_code        ON classrooms(join_code)",
            "CREATE INDEX IF NOT EXISTS idx_classroom_students_student  ON classroom_students(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_classroom_students_class    ON classroom_students(classroom_id)",
            # ── Sprint 2: course builder (012) ──────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS courses (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                teacher_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                description TEXT,
                subject     TEXT,
                grade       TEXT,
                status      TEXT NOT NULL DEFAULT 'draft',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS course_units (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                course_id   UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                title       TEXT NOT NULL,
                description TEXT,
                position    INT  NOT NULL DEFAULT 0,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS course_concepts (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                unit_id      UUID NOT NULL REFERENCES course_units(id) ON DELETE CASCADE,
                title        TEXT NOT NULL,
                description  TEXT,
                study_set_id UUID REFERENCES study_sets(id) ON DELETE SET NULL,
                position     INT  NOT NULL DEFAULT 0,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS classroom_courses (
                classroom_id UUID REFERENCES classrooms(id) ON DELETE CASCADE,
                course_id    UUID REFERENCES courses(id)    ON DELETE CASCADE,
                assigned_at  TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (classroom_id, course_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_courses_teacher          ON courses(teacher_id)",
            "CREATE INDEX IF NOT EXISTS idx_course_units_course      ON course_units(course_id, position)",
            "CREATE INDEX IF NOT EXISTS idx_course_concepts_unit     ON course_concepts(unit_id, position)",
            "CREATE INDEX IF NOT EXISTS idx_classroom_courses_course ON classroom_courses(course_id)",
            # ── Sprint 3: student concept progress (013) ────────────────────────
            """
            CREATE TABLE IF NOT EXISTS student_concept_progress (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                student_id    UUID NOT NULL REFERENCES users(id)            ON DELETE CASCADE,
                concept_id    UUID NOT NULL REFERENCES course_concepts(id)  ON DELETE CASCADE,
                course_id     UUID NOT NULL REFERENCES courses(id)          ON DELETE CASCADE,
                visited       BOOLEAN     NOT NULL DEFAULT false,
                visited_at    TIMESTAMPTZ,
                quiz_score    FLOAT,
                quiz_taken_at TIMESTAMPTZ,
                last_seen_at  TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (student_id, concept_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_scp_student        ON student_concept_progress(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_scp_student_course ON student_concept_progress(student_id, course_id)",
            # ── Sprint 4: concept content / syllabus storage (014) ─────────────
            "ALTER TABLE courses ADD COLUMN IF NOT EXISTS syllabus_pdf      BYTEA",
            "ALTER TABLE courses ADD COLUMN IF NOT EXISTS syllabus_filename TEXT",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS content_text TEXT",
            """
            CREATE TABLE IF NOT EXISTS concept_images (
                id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
                concept_id UUID         NOT NULL REFERENCES course_concepts(id) ON DELETE CASCADE,
                data       BYTEA        NOT NULL,
                mime_type  TEXT         NOT NULL DEFAULT 'image/jpeg',
                caption    TEXT,
                position   INT          NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ           DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_concept_images_concept ON concept_images(concept_id, position)",
            # ── Sprint 5: AI concept pipeline (015) ─────────────────────────────
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS source_text     TEXT",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS ai_summary      TEXT",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS ai_transcript   TEXT",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS pipeline_status TEXT NOT NULL DEFAULT 'draft'",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS approved_at     TIMESTAMPTZ",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS chapter_ref     TEXT",
            """
            CREATE TABLE IF NOT EXISTS course_chapters (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                course_id     UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                filename      TEXT NOT NULL,
                page_count    INT,
                concept_count INT,
                status        TEXT NOT NULL DEFAULT 'processing',
                error_msg     TEXT,
                created_at    TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_course_chapters_course ON course_chapters(course_id)",
            "CREATE INDEX IF NOT EXISTS idx_concept_pipeline       ON course_concepts(pipeline_status)",
            # ── Sprint 6: AI asset generation per concept (016) ─────────────────
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS quiz_status        TEXT NOT NULL DEFAULT 'none'",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS flashcard_status   TEXT NOT NULL DEFAULT 'none'",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS audio_status       TEXT NOT NULL DEFAULT 'none'",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS audio_data         BYTEA",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS audio_duration_sec INT",
            """
            CREATE TABLE IF NOT EXISTS concept_quiz_questions (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                concept_id  UUID NOT NULL REFERENCES course_concepts(id) ON DELETE CASCADE,
                question    TEXT NOT NULL,
                options     JSONB NOT NULL,
                correct_idx INT  NOT NULL,
                explanation TEXT,
                position    INT  NOT NULL DEFAULT 0,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS concept_flashcards (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                concept_id  UUID NOT NULL REFERENCES course_concepts(id) ON DELETE CASCADE,
                front       TEXT NOT NULL,
                back        TEXT NOT NULL,
                position    INT  NOT NULL DEFAULT 0,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_quiz_concept        ON concept_quiz_questions(concept_id)",
            "CREATE INDEX IF NOT EXISTS idx_flashcards_concept  ON concept_flashcards(concept_id)",
            "CREATE INDEX IF NOT EXISTS idx_concept_audio       ON course_concepts(audio_status)",
            # ── Sprint 6 follow-up: chapter PDF storage + concept video (017) ──
            "ALTER TABLE course_chapters ADD COLUMN IF NOT EXISTS pdf_data BYTEA",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS video_data   BYTEA",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS video_status TEXT NOT NULL DEFAULT 'none'",
            "CREATE INDEX IF NOT EXISTS idx_concept_video ON course_concepts(video_status)",
            # ── Surface concept video generation errors to the teacher UI (018) ─
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS video_error TEXT",
            # ── Concept videos now render via the Manim/Cloud Run pipeline (019) ─
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS video_job_id INTEGER REFERENCES videos(id) ON DELETE SET NULL",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS video_url TEXT",
            # ── Sprint 7: spaced-repetition review log for concept flashcards (020) ─
            """
            CREATE TABLE IF NOT EXISTS concept_flashcard_reviews (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                student_id   UUID NOT NULL REFERENCES users(id)              ON DELETE CASCADE,
                flashcard_id UUID NOT NULL REFERENCES concept_flashcards(id) ON DELETE CASCADE,
                rating       INT NOT NULL,
                reviewed_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_concept_flashcard_reviews_student ON concept_flashcard_reviews(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_concept_flashcard_reviews_card    ON concept_flashcard_reviews(flashcard_id)",
            # ── Sprint 7: real spaced-repetition scheduling state (021) ──────────
            """
            CREATE TABLE IF NOT EXISTS study_flashcard_state (
                id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                student_id       UUID NOT NULL REFERENCES users(id)            ON DELETE CASCADE,
                flashcard_id     UUID NOT NULL REFERENCES study_flashcards(id) ON DELETE CASCADE,
                repetitions      INT NOT NULL DEFAULT 0,
                ease_factor      FLOAT NOT NULL DEFAULT 2.5,
                interval_days    FLOAT NOT NULL DEFAULT 0,
                due_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_reviewed_at TIMESTAMPTZ,
                UNIQUE (student_id, flashcard_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS concept_flashcard_state (
                id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                student_id       UUID NOT NULL REFERENCES users(id)              ON DELETE CASCADE,
                flashcard_id     UUID NOT NULL REFERENCES concept_flashcards(id) ON DELETE CASCADE,
                repetitions      INT NOT NULL DEFAULT 0,
                ease_factor      FLOAT NOT NULL DEFAULT 2.5,
                interval_days    FLOAT NOT NULL DEFAULT 0,
                due_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_reviewed_at TIMESTAMPTZ,
                UNIQUE (student_id, flashcard_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_sfs_student_due ON study_flashcard_state(student_id, due_at)",
            "CREATE INDEX IF NOT EXISTS idx_cfs_student_due ON concept_flashcard_state(student_id, due_at)",
            # ── Sprint 9: direct teacher <-> student messaging (022) ──────────────
            """
            CREATE TABLE IF NOT EXISTS teacher_student_messages (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                teacher_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                sender_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body        TEXT NOT NULL,
                read_at     TIMESTAMPTZ,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_tsm_pair    ON teacher_student_messages(teacher_id, student_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_tsm_student  ON teacher_student_messages(student_id, created_at)",
            # ── Sprint 9: differentiated per-student assignments (023) ────────────
            """
            CREATE TABLE IF NOT EXISTS student_assignments (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                teacher_id    UUID NOT NULL REFERENCES users(id)            ON DELETE CASCADE,
                student_id    UUID NOT NULL REFERENCES users(id)            ON DELETE CASCADE,
                concept_id    UUID REFERENCES course_concepts(id)           ON DELETE SET NULL,
                kind          TEXT NOT NULL,
                title         TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'generating',
                payload       JSONB,
                study_set_id  UUID REFERENCES study_sets(id)                ON DELETE SET NULL,
                video_job_id  INTEGER REFERENCES videos(id)                 ON DELETE SET NULL,
                error_message TEXT,
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                completed_at  TIMESTAMPTZ
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_sa_student ON student_assignments(student_id, created_at)",
            # ── Teacher-led concept creation: image-crop selection + optional AI ──
            "ALTER TABLE course_units ADD COLUMN IF NOT EXISTS chapter_ref UUID REFERENCES course_chapters(id) ON DELETE SET NULL",
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'ai'",
            # ── Per-concept authoring chat (teacher-only) ─────────────────────────
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS concept_id UUID REFERENCES course_concepts(id) ON DELETE CASCADE",
            # ── Concept supplementary resources (images, PDFs, videos) ────────────
            """
            CREATE TABLE IF NOT EXISTS concept_resources (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                concept_id  UUID NOT NULL REFERENCES course_concepts(id) ON DELETE CASCADE,
                type        TEXT NOT NULL,
                title       TEXT NOT NULL DEFAULT '',
                file_data   BYTEA,
                mime_type   TEXT,
                raw_text    TEXT,
                video_url   TEXT,
                position    INT  NOT NULL DEFAULT 0,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_concept_resources_concept ON concept_resources(concept_id, position)",
            # ── Store PDF bytes in DB so proxy never depends on R2 read access ───
            "ALTER TABLE study_materials ADD COLUMN IF NOT EXISTS file_data BYTEA",
            # ── Per-study-concept chat conversations ──────────────────────────────
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS study_concept_id UUID REFERENCES study_concepts(id) ON DELETE CASCADE",
            # ── Teacher Studio: chapter-level authoring chat ──────────────────
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS chapter_id UUID REFERENCES course_chapters(id) ON DELETE CASCADE",
            # ── Videos: link to concept (1-to-many) ──────────────────────────
            "ALTER TABLE videos ADD COLUMN IF NOT EXISTS concept_id UUID REFERENCES course_concepts(id) ON DELETE SET NULL",
            "CREATE INDEX IF NOT EXISTS idx_videos_concept ON videos(concept_id)",
            # ── Concept textbook content blocks (ordered, typed) ──────────────
            """
            CREATE TABLE IF NOT EXISTS concept_content_blocks (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                concept_id  UUID    NOT NULL REFERENCES course_concepts(id) ON DELETE CASCADE,
                type        TEXT    NOT NULL DEFAULT 'text',
                position    INTEGER NOT NULL DEFAULT 0,
                title       TEXT,
                body        TEXT,
                video_id    INTEGER REFERENCES videos(id) ON DELETE SET NULL,
                created_by  UUID    REFERENCES users(id) ON DELETE SET NULL,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_content_blocks_concept ON concept_content_blocks(concept_id, position)",
            # ── Per-block audio (TTS generated per textbook card) ─────────────
            "ALTER TABLE concept_content_blocks ADD COLUMN IF NOT EXISTS audio_data BYTEA",
            "ALTER TABLE concept_content_blocks ADD COLUMN IF NOT EXISTS audio_status TEXT NOT NULL DEFAULT 'none'",
            # in_textbook: false = studio-generated block (tracking only), true = visible in textbook
            "ALTER TABLE concept_content_blocks ADD COLUMN IF NOT EXISTS in_textbook BOOLEAN NOT NULL DEFAULT true",
            # audio_script: formula-free transcript text used as TTS source instead of block body
            "ALTER TABLE concept_content_blocks ADD COLUMN IF NOT EXISTS audio_script TEXT",
            # source_message_id: tracks which chat message a block was imported from (via apply)
            "ALTER TABLE concept_content_blocks ADD COLUMN IF NOT EXISTS source_message_id UUID REFERENCES messages(id) ON DELETE SET NULL",
            # ── Tag studio/authoring conversations so sidebar can exclude them ──
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS conversation_type TEXT NOT NULL DEFAULT 'chat'",
            "UPDATE conversations SET conversation_type = 'studio' WHERE concept_id IS NOT NULL AND conversation_type = 'chat'",
            # ── Quiz/flashcard per-item draft review ──────────────────────────
            "ALTER TABLE concept_quiz_questions ADD COLUMN IF NOT EXISTS status     TEXT NOT NULL DEFAULT 'approved'",
            "ALTER TABLE concept_quiz_questions ADD COLUMN IF NOT EXISTS difficulty TEXT NOT NULL DEFAULT 'medium'",
            "ALTER TABLE concept_flashcards     ADD COLUMN IF NOT EXISTS status     TEXT NOT NULL DEFAULT 'approved'",
            "ALTER TABLE course_concepts        ADD COLUMN IF NOT EXISTS quiz_mode  TEXT NOT NULL DEFAULT 'ordered'",
            # ── Concept source page within its chapter PDF ────────────────────
            "ALTER TABLE course_concepts ADD COLUMN IF NOT EXISTS page_start INTEGER",
            # ── Phase 3 progress: per-attempt quiz log ────────────────────────
            """
            CREATE TABLE IF NOT EXISTS concept_quiz_attempts (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                student_id  UUID NOT NULL REFERENCES users(id)            ON DELETE CASCADE,
                concept_id  UUID NOT NULL REFERENCES course_concepts(id)  ON DELETE CASCADE,
                score       FLOAT NOT NULL,
                taken_at    TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_concept ON concept_quiz_attempts(student_id, concept_id, taken_at)",
            # Store per-question answers so teachers can see which questions trip students up
            "ALTER TABLE concept_quiz_attempts ADD COLUMN IF NOT EXISTS answers JSONB",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS audio_data   BYTEA",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS audio_script TEXT",
            # ── Phase 3 progress: daily time-on-page per concept ─────────────
            """
            CREATE TABLE IF NOT EXISTS concept_time_logs (
                student_id   UUID NOT NULL REFERENCES users(id)            ON DELETE CASCADE,
                concept_id   UUID NOT NULL REFERENCES course_concepts(id)  ON DELETE CASCADE,
                log_date     DATE NOT NULL DEFAULT CURRENT_DATE,
                seconds_spent INT NOT NULL DEFAULT 0,
                PRIMARY KEY (student_id, concept_id, log_date)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_time_logs_student ON concept_time_logs(student_id, concept_id)",
            # ── Phase 3 progress: max video watch % per student × concept × block ─
            # block_id = content-block UUID, or 'legacy' for old single-video concepts
            """
            CREATE TABLE IF NOT EXISTS concept_video_watches (
                student_id   UUID  NOT NULL REFERENCES users(id)            ON DELETE CASCADE,
                concept_id   UUID  NOT NULL REFERENCES course_concepts(id)  ON DELETE CASCADE,
                block_id     TEXT  NOT NULL DEFAULT 'legacy',
                pct_watched  FLOAT NOT NULL DEFAULT 0,
                updated_at   TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (student_id, concept_id, block_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_video_watches_student ON concept_video_watches(student_id, concept_id)",
            # Upgrade: add block_id column if the table already existed without it
            "ALTER TABLE concept_video_watches ADD COLUMN IF NOT EXISTS block_id TEXT NOT NULL DEFAULT 'legacy'",
            # Upgrade: rebuild PK to include block_id (idempotent via exception handling)
            """
            DO $$ BEGIN
              BEGIN
                ALTER TABLE concept_video_watches DROP CONSTRAINT concept_video_watches_pkey;
              EXCEPTION WHEN others THEN NULL;
              END;
              BEGIN
                ALTER TABLE concept_video_watches ADD PRIMARY KEY (student_id, concept_id, block_id);
              EXCEPTION WHEN others THEN NULL;
              END;
            END $$
            """,
            # ── Expand language check constraint to include Spanish and French ─────
            """
            DO $$ BEGIN
              BEGIN
                ALTER TABLE users DROP CONSTRAINT users_language_check;
              EXCEPTION WHEN others THEN NULL;
              END;
              BEGIN
                ALTER TABLE users ADD CONSTRAINT users_language_check
                  CHECK (language IN ('en', 'fi', 'sv', 'es', 'fr'));
              EXCEPTION WHEN others THEN NULL;
              END;
            END $$
            """,
        ]:
            try:
                await db.execute(sql)
                _log.info("Migration OK: %s", sql.strip()[:60])
            except Exception as exc:
                _log.error("Migration FAILED: %s — %s", sql.strip()[:60], exc)
    yield
    await close_pool()


app = FastAPI(title="Learn-AI API", version="1.0.0", lifespan=lifespan)

_allowed_origins: list[str] = list({
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "https://learnx-ai.com",
    "https://www.learnx-ai.com",
    "https://learn-ai-ebon.vercel.app",   # Vercel preview
    *[o.strip() for o in settings.EXTRA_ALLOWED_ORIGINS.split(",") if o.strip()],
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(videos.router)
app.include_router(quizzes.router)
app.include_router(uploads.router)
app.include_router(studysets.router)
app.include_router(images.router)
app.include_router(teacher_auth.router)
app.include_router(institutions.router)
app.include_router(admin.router)
app.include_router(classrooms.router)
app.include_router(courses.router)
app.include_router(students.router)
app.include_router(messages.router)
app.include_router(assignments.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    """Check DB schema — shows columns on users table and all public tables."""
    from database import get_db
    result: dict = {}
    async with get_db() as db:
        cols = await db.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users'
            ORDER BY ordinal_position
        """)
        result["users_columns"] = [r["column_name"] for r in cols]
        result["has_password_hash"] = "password_hash" in result["users_columns"]
        result["has_google_id"]     = "google_id"     in result["users_columns"]

        tables = await db.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        result["tables"] = [r["table_name"] for r in tables]
        result["has_student_profiles"] = "student_profiles" in result["tables"]

        # Test register INSERT inside a real transaction (rolled back)
        try:
            async with db.transaction():
                await db.execute(
                    "INSERT INTO users (email, password_hash) VALUES ($1, $2)",
                    "__healthcheck__@learnai.internal", "x",
                )
                raise Exception("rollback")   # force rollback
        except Exception as exc:
            rolled_back = str(exc) == "rollback"
            result["register_insert_ok"] = rolled_back
            if not rolled_back:
                result["register_insert_error"] = str(exc)

    return result


@app.get("/health/r2")
async def health_r2():
    """Debug endpoint — tests R2 connectivity and returns the actual error if any."""
    import re
    from config import settings
    from services.manim import _make_r2_client, R2_BUCKET_NAME, R2_PUBLIC_URL

    account_id = settings.R2_ACCOUNT_ID or ""
    result = {
        "R2_ACCOUNT_ID":        account_id[:6] + "…" if account_id else "(not set)",
        "R2_ACCOUNT_ID_valid":  bool(re.fullmatch(r"[a-fA-F0-9]{32}", account_id)),
        "R2_ACCESS_KEY_ID":     (settings.R2_ACCESS_KEY_ID or "")[:6] + "…" if settings.R2_ACCESS_KEY_ID else "(not set)",
        "R2_SECRET_KEY_set":    bool(settings.R2_SECRET_ACCESS_KEY),
        "R2_BUCKET_NAME":       R2_BUCKET_NAME or "(not set)",
        "R2_PUBLIC_URL":        R2_PUBLIC_URL or "(not set)",
        "client_created":       False,
        "put_object_ok":        False,
        "error":                None,
    }

    r2 = _make_r2_client()
    if not r2:
        result["error"] = "Client not created — check R2_ACCOUNT_ID (must be 32 hex chars)"
        return result

    result["client_created"] = True
    try:
        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key="health-check/ping.txt",
            Body=b"ok",
            ContentType="text/plain",
        )
        result["put_object_ok"] = True
    except Exception as exc:
        result["error"] = str(exc)

    return result
