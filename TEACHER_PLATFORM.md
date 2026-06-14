# LearnX Teacher Platform — Requirements & Implementation Plan

AI-powered classroom platform where teachers orchestrate learning and students consume
within a teacher-defined, AI-assisted environment.

---

## Table of Contents

1. [Overview](#overview)
2. [Portals](#portals)
3. [Feature Requirements](#feature-requirements)
   - [Classroom Management](#1-classroom-management)
   - [Course & Study Plan Builder](#2-course--study-plan-builder)
   - [Custom Content Creation](#3-custom-content-creation)
   - [Assignment System](#4-assignment-system)
   - [Question Bank](#5-question-bank)
   - [Student AI Chat (Scoped)](#6-student-ai-chat-scoped)
   - [Individual Student Tracking](#7-individual-student-tracking)
   - [Student Grouping](#8-student-grouping)
   - [Needs Attention System](#9-needs-attention-system)
   - [Teacher ↔ Student Interaction](#10-teacher--student-interaction)
   - [Student View](#11-student-view)
   - [Teacher Dashboard](#12-teacher-dashboard)
4. [Data Model](#data-model)
5. [Implementation Plan](#implementation-plan)

---

## Overview

Two portals, one backend. Teachers configure, observe, and intervene. Students
experience content and progress through the plan.

**Core principle:** Teacher's own voice and content, amplified by AI rather than replaced by it.
Nothing reaches students without teacher approval.

**What makes this different from Google Classroom:**

| Google Classroom | LearnX Teacher |
|---|---|
| Upload files, link YouTube | Upload + AI improves + approve + publish |
| Grade manually | AI pre-grades, teacher reviews |
| No AI tutoring | AI tutor scoped to teacher's syllabus |
| No learning behaviour signals | Behavioural analytics (rewatch, AI usage, pace) |
| Static groups | Dynamic groups by performance rule |
| No video generation | Teacher scripts → Manim video pipeline |
| General chat | Concept-anchored, transcript-aware teacher notes |

---

## Portals

Two separate experiences under one login — role switch based on `user.role`:

- **`/teacher/...`** — Teacher portal (separate subdomain: `teach.learnx-ai.com`)
- **`/student/...`** — Student portal (same app, scoped view)

The same concept page (`/classroom/:id/concept/:cid`) renders differently based on role:

**Teacher sees:** class-wide performance signals, edit controls, student question patterns, flags raised  
**Student sees:** personal checklist, content to consume, AI chat, flag button

---

## Feature Requirements

---

### 1. Classroom Management

**Teacher can:**
- Create a classroom with a name, subject, grade level, and syllabus scope description
- Generate a join code or shareable invite link for students
- Bulk-import students via CSV (name + email)
- Connect to Google Classroom for student roster import
- Remove students or mark them inactive
- Archive a classroom at end of term (data retained, read-only)

**Student can:**
- Join a classroom via join code or invite link
- See all classrooms they belong to on their dashboard

---

### 2. Course & Study Plan Builder

Hierarchy: **Course → Units → Concepts**

**Teacher can:**
- Create a course and attach it to one or more classrooms
- Add units (chapters) within a course, set order
- Add concepts within each unit, set order
- Per concept, attach any combination of:
  - PDF / reading material
  - Custom image (teacher uploaded)
  - Custom script / lesson notes (with AI improvement option)
  - Teacher-recorded video (uploaded from laptop)
  - AI-generated Manim video (triggered by teacher)
  - AI-generated quiz (with approval workflow)
  - Teacher-written quiz questions
  - Teacher annotation / personal note to students
- Lock/unlock concepts by date OR by prerequisite (student must complete concept N before N+1)
- Preview the concept exactly as a student will see it

**Student sees:**
- Concept checklist: watch video → read notes → take quiz → ask AI
- Locked concepts shown greyed out with unlock condition
- Personal completion status per item

---

### 3. Custom Content Creation

#### 3a. Custom Image Upload

- Teacher uploads JPG/PNG/SVG (hand-drawn diagrams, whiteboard photos, textbook scans, lab photos)
- On upload, AI auto-generates a caption and alt-text — teacher reviews and edits
- Teacher can optionally check "Expand description with AI":
  - AI analyses the image and writes a detailed educational explanation
  - Teacher sees a side-by-side diff (original vs AI), accepts/edits/rejects line by line
- Final description becomes part of the concept's knowledge base — student AI can reference it
- **Phase 2:** In-browser annotation layer — teacher draws arrows and labels on the image

#### 3b. Script / Lesson Notes Editor

- Teacher writes rough notes or a full script in a text editor
- AI improvement modes (teacher picks one before clicking Improve):
  - **Polish** — fix grammar, preserve teacher's voice and examples
  - **Expand** — add depth, worked examples, fill gaps
  - **Simplify** — rewrite for the classroom's grade level
  - **Structure** — convert rough notes into: Intro → Explanation → Example → Summary
- Side-by-side diff view: teacher's version vs AI version, accept line by line or all at once
- Final script serves two purposes:
  1. Readable concept summary displayed to students
  2. Narration fed into the Manim video pipeline (bypasses AI script-writing step)

#### 3c. Script → Video

- Teacher clicks "Generate video from this script"
- Script becomes the narration track — teacher's words, AI-animated visuals
- Same Manim pipeline as existing platform, no new infrastructure needed
- Teacher reviews the generated video before publishing

#### 3d. Teacher Video Upload

- Teacher uploads `.mp4`, `.mov`, `.webm` from their laptop (up to 2 GB)
- Platform transcribes audio via Whisper / Azure STT
- Transcript shown for teacher review and editing (correct mistakes, add missed words)
- AI generates chapter markers from transcript: `0:00 Intro`, `1:30 The Formula`, `3:45 Worked Example`
- Transcript stored as searchable text — students can search within the video
- Transcript becomes part of concept knowledge base:
  - Student AI can answer "What did the teacher say about X at 2:30?" using the transcript
  - Teacher can edit transcript to add corrections after the fact

---

### 4. Assignment System

#### Assignment Types

| Type | Description |
|---|---|
| **Quiz retry** | Student retakes quiz with freshly generated questions (different set, same concept) |
| **Extra concept** | Assign a concept not in the main course plan — only visible to assigned student/group |
| **Problem set** | AI generates N problems on a topic; teacher reviews before assigning |
| **Reading + reflection** | Attach PDF, student writes a summary; AI gives feedback, teacher reviews |
| **Peer challenge** | Same problem sent to two students; they submit independently, then see each other's approach |

#### Assignment Creation Flow

1. Teacher spots a struggling student or group
2. Clicks "Assign extra work" from student profile or attention queue
3. Picks assignment type
4. Sets due date and adds a personal note to the student
5. For AI-generated content (problem sets, quizzes): goes through approval workflow before being sent
6. Student is notified when assignment is created

#### Student Assignment Experience

- Notification: "New assignment from Mr. Smith — due Friday"
- Opens assignment with teacher's personal note
- Works through it with scoped AI (constrained to the assignment topic)
- Submits
- Sees teacher feedback after submission

---

### 5. Question Bank

- Every question a teacher writes or approves from AI is saved to their personal question bank
- Tagged by: topic, difficulty (Easy / Medium / Hard), type (MCQ / Short answer / Calculation)
- Searchable: teacher types "momentum" and sees all questions on that topic
- Reusable: pull from the bank when building any future assignment — don't rebuild from scratch
- AI-generated questions that are approved also enter the bank

#### Question Builder — Three Modes

**Mode 1: Write from scratch**
- Fields: question text, answer options (MCQ) or answer (short/calculation), correct answer, explanation, marks, difficulty
- "Improve this question with AI" button — AI refines wording, adds a clearer explanation

**Mode 2: AI generates batch, teacher approves**
- Teacher sets: topic, number of questions, difficulty, type
- AI generates the batch
- Teacher sees a review queue: one question per card
- Per question: Approve / Edit / Regenerate / Reject
- Approved go into the assignment and question bank; rejected are discarded

**Mode 3: Mix**
- Teacher writes N questions they specifically want
- Says "AI, generate M more in the same style"
- AI matches style and difficulty; teacher reviews the AI-generated portion

---

### 6. Student AI Chat (Scoped)

**How it differs from the main platform AI:**

- Hard-scoped to the current course syllabus and concept materials
- Incorporates teacher's uploaded content (images, script, video transcript) as knowledge base
- System prompt includes: course name, teacher name, list of concepts, boundary instruction
- If student asks outside scope: "That's outside what we're covering — ask your teacher"
- Tone set by teacher: Direct / Socratic (AI asks follow-up questions back) / Formal

**System prompt structure:**
```
You are a tutor for [Course Name] taught by [Teacher Name].
Grade level: [Grade]. Subject: [Subject].

You may ONLY answer questions related to these concepts:
[concept list]

The student's materials for the current concept include:
[script / image descriptions / video transcript]

Tone: [Socratic | Direct | Formal]

If a student asks about anything outside this scope, respond:
"That's outside what we're covering in this class — ask your teacher directly."
```

**Teacher visibility:**
- Teacher can read all student AI chat transcripts per concept
- AI chat volume per concept is surfaced in the performance dashboard (high volume = confusion signal)

---

### 7. Individual Student Tracking

Teacher clicks any student to see a full learning portrait — behaviour signals, not just grades.

**Data shown per student:**
- Progress: completion % per unit, quiz score history per concept
- Behaviour signals:
  - Average time spent per concept
  - Number of quiz retakes (positive signal — they care)
  - AI chat volume (high = may be struggling)
  - Videos rewatched (which ones and how many times)
  - Flags raised
  - Last active date
- AI chat summary: "She keeps asking about the difference between velocity and acceleration — 7 questions this week"
- Best and worst concepts by score

**One-click actions from student profile:**
- Assign extra work
- Send message
- Add to group

---

### 8. Student Grouping

#### Three Group Types

**Auto-groups (AI-suggested)**
- System clusters students based on performance patterns
- Groups: Struggling / On Track / Advanced
- Teacher sees suggested grouping and can accept, modify, or ignore

**Manual groups**
- Teacher drags students into named groups
- e.g. "Needs support on Unit 2", "Lab partners", "Advanced track"
- Groups are reusable across assignments

**Dynamic groups (rule-based)**
- Teacher sets a rule: "Anyone with quiz average below 65% on Unit 2"
- Students flow in and out automatically as scores change
- Teacher assigns work to the rule — it stays current without manual updates

---

### 9. Needs Attention System

Teacher dashboard surfaces struggling students automatically — no hunting required.

**Signals that trigger an alert:**
- Failed the same quiz 3+ times
- No activity in 5+ days
- Quiz score dropped more than 20% between attempts
- Raised 3+ unanswered flags
- AI chat volume spike on a specific concept (class-wide confusion)
- Finished early (needs extension work)

**Attention queue (inbox-style on dashboard):**
- Each card shows the student, the signal, and one-click actions
- Actions inline — teacher doesn't navigate away
- Examples: Assign retry / Message / Add to support group / Send nudge / Assign extension

---

### 10. Teacher ↔ Student Interaction

#### Async (default, always available)

- Teacher leaves a text or voice note on a specific concept or assignment
- Student sees it when opening that concept: notification badge
- Student replies — thread stays attached to that concept (not general inbox)
- Teacher notified of reply

#### Student Flags

- Student clicks "Flag for teacher" on any concept or AI response
- Writes a short message ("I don't understand why F=ma and not F=m+a")
- Teacher sees flags in the attention queue and on the concept page
- Teacher resolves the flag with a reply or voice note

#### Live Session (Phase 4)

- Teacher opens a live session on a concept
- All students in the class get a push notification: "Mr. Smith is live — join now"
- Students submit questions via text; teacher answers verbally
- Session is recorded and automatically attached to the concept
- Students who missed it can watch the recording

---

### 11. Student View

**Dashboard answers: "What do I do today?"**
- Next concept in the plan (prominent CTA)
- Daily streak and study goal
- Quiz scores and recent badges
- "Your teacher left a note" notification
- Upcoming quiz deadlines

**Concept page (student):**
- Personal checklist: watch video / read notes / take quiz / ask AI
- Teacher's personal note shown prominently
- Quiz: attempt, see score, retake if allowed
- AI chat button — opens scoped AI for this concept only
- Flag button — raise a question for the teacher

**Assignments:**
- Separate tab: "My Assignments"
- Due date, type, teacher's note
- Status: Not started / In progress / Submitted / Reviewed

**Progress view:**
- Completion % per unit
- Quiz score history with trend line
- Time studied this week
- Class average comparison (teacher can hide this)

---

### 12. Teacher Dashboard

**Answers: "What needs my attention right now?"**

- Attention queue (inbox): flagged students and signals, one-click actions
- Class completion heatmap: which concepts have low completion rates
- Quiz performance: class average per concept, concepts below 70% highlighted
- Engagement timeline: daily activity chart — did engagement drop this week?
- Upcoming unlocks: concepts going live in the next 7 days
- Recent AI chat activity: topic clusters — what is the class confused about?

---

## Data Model

```sql
-- Classrooms
classrooms (
  id, teacher_id, name, join_code,
  subject, grade, syllabus_scope,
  created_at, archived_at
)

-- Roster
classroom_students (
  classroom_id, student_id,
  joined_at, status  -- active | removed
)

-- Course structure
courses    (id, classroom_id, title, description, created_at)
units      (id, course_id, title, order_index, unlock_at)
concepts   (
  id, unit_id, title, order_index,
  script_teacher TEXT,       -- teacher's raw notes
  script_final TEXT,         -- approved final version
  ai_improvement_mode TEXT,  -- polish|expand|simplify|structure
  teacher_note TEXT,
  ai_tone TEXT,              -- direct|socratic|formal
  unlock_after_concept_id,   -- prerequisite
  unlock_at TIMESTAMPTZ,
  created_at
)

-- Concept attachments
concept_images (
  id, concept_id, url, caption,
  ai_description TEXT, teacher_approved BOOL
)
concept_videos (
  id, concept_id, source TEXT,  -- manim|teacher_upload|script
  video_url TEXT, transcript TEXT,
  chapter_markers JSONB, duration_secs INT
)

-- Student progress
student_progress (
  classroom_id, student_id, concept_id,
  status TEXT,        -- not_started|in_progress|complete
  quiz_score INT,
  quiz_attempts INT,
  time_spent_secs INT,
  ai_chat_count INT,
  video_rewatch_count INT,
  last_seen_at TIMESTAMPTZ
)

-- Groups
student_groups (
  id, classroom_id, teacher_id,
  name TEXT,
  type TEXT,          -- manual|dynamic
  rule_json JSONB,    -- for dynamic: {field, operator, value}
  created_at
)
student_group_members (
  group_id, student_id,
  added_at, added_by TEXT  -- teacher|auto
)

-- Assignments
assignments (
  id, classroom_id, teacher_id,
  title TEXT, type TEXT,
  target_type TEXT,   -- student|group
  target_id TEXT,
  concept_id,
  due_at TIMESTAMPTZ,
  teacher_note TEXT,
  config_json JSONB,  -- {n_questions, difficulty, etc.}
  status TEXT,        -- draft|active|closed
  created_at
)
assignment_submissions (
  id, assignment_id, student_id,
  content TEXT,
  score INT,
  submitted_at TIMESTAMPTZ,
  teacher_feedback TEXT,
  reviewed_at TIMESTAMPTZ
)

-- Question bank
questions (
  id, teacher_id, concept_id,
  body TEXT, type TEXT,        -- mcq|short|calculation
  options JSONB,               -- [{text, correct}]
  answer TEXT, explanation TEXT,
  difficulty TEXT, marks INT,
  source TEXT,                 -- teacher|ai_approved
  created_at
)

-- Teacher ↔ student interaction
teacher_comments (
  id, concept_id, assignment_id,
  teacher_id, student_id,      -- null = visible to all
  body TEXT, voice_url TEXT,
  created_at
)
student_flags (
  id, concept_id, student_id,
  message TEXT,
  resolved BOOL, resolved_at TIMESTAMPTZ,
  teacher_reply TEXT, created_at
)

-- Attention signals
attention_signals (
  id, classroom_id, student_id,
  signal_type TEXT,   -- quiz_failed_3x|inactive_5d|score_drop|flag_backlog|early_finisher
  concept_id,
  resolved BOOL, created_at
)
```

---

## Implementation Plan

### Codebase Observations (as of June 2026)

Before estimating effort, three facts from the existing code that change the plan:

**1. No `role` on users.**
`users` table has `tier` (free/learner/pro) but nothing that distinguishes teacher from student.
Adding `account_type TEXT DEFAULT 'student'` is the very first change needed — everything gates on it.

**2. A study set IS a concept.**
`study_sets` + `study_concepts` + `study_materials` + `study_flashcards` + the
chat/quiz/video/image pipeline is exactly what the teacher platform needs per concept.
The teacher platform is an **organisational and permission wrapper around study sets**,
not a parallel content system. No new content pipeline needs to be built.

**3. `studysets.py` already has everything.**
Upload, concept extraction, chat (with system prompt scoping), quiz generation, video trigger,
image generation, status polling — all working. The study set chat endpoint is also the
classroom concept chat endpoint; it just needs classroom context injected into the system prompt.

**Net effect on estimates:** the original 22-week plan shrinks to ~16 weeks.
The PDF pipeline and AI scoping being pre-built saves roughly 6 weeks.

---

### Key Design Decision: Concepts Reuse Study Sets

Rather than creating a new `concepts` table, a concept in the teacher platform IS a study set.
Add three columns to `study_sets`:

```sql
ALTER TABLE study_sets ADD COLUMN unit_id UUID REFERENCES units(id);
ALTER TABLE study_sets ADD COLUMN order_index INT DEFAULT 0;
ALTER TABLE study_sets ADD COLUMN is_classroom_concept BOOL DEFAULT FALSE;
ALTER TABLE study_sets ADD COLUMN unlock_at TIMESTAMPTZ;
ALTER TABLE study_sets ADD COLUMN teacher_note TEXT;
```

A `study_set` is then either:
- A personal study set owned by a student (`is_classroom_concept = FALSE`, `unit_id = NULL`)
- A classroom concept owned by a teacher (`is_classroom_concept = TRUE`, `unit_id` set)

Same pipeline. Same endpoints. New context.

---

### Sprint 0 — Week 1: Institutions + Teacher Accounts + Separate Auth Portal

**Goal:** Two distinct onboarding paths exist — one for teachers/institutions, one for students.
No teacher or institution can access the platform without going through the right gate.
Students are completely unaffected by any of this.

---

#### Two Business Models, One Backend

```
Standalone teacher   →  invited individually by you  →  no institution_id
Institution          →  school / tuition center signs up  →  admin activates teachers and students
```

Both use the same classrooms, courses, concepts pipeline.
`institution_id NULL` on a classroom = standalone teacher.
`institution_id SET` = belongs to a school, institution admin can see it.

---

#### Migration (`009_institutions.sql`)

```sql
-- Institution (school, tuition center, university, coaching institute)
CREATE TABLE institutions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL,
  type         TEXT NOT NULL,         -- school | tuition_center | university | coaching
  email_domain TEXT,                  -- e.g. 'helsinki-hs.edu' → auto-verify members
  country      TEXT,
  plan         TEXT DEFAULT 'trial',  -- trial | pro | enterprise
  max_teachers INT DEFAULT 5,         -- trial cap
  max_students INT DEFAULT 50,        -- trial cap
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Who belongs to which institution and in what role
CREATE TABLE institution_members (
  institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
  user_id        UUID REFERENCES users(id) ON DELETE CASCADE,
  role           TEXT NOT NULL,         -- admin | teacher | student
  status         TEXT DEFAULT 'active', -- active | suspended | pending
  invited_by     UUID REFERENCES users(id),
  joined_at      TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (institution_id, user_id)
);

-- Teacher invite codes (standalone teachers, not under an institution)
CREATE TABLE teacher_invites (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code       TEXT UNIQUE NOT NULL DEFAULT substr(md5(random()::text), 1, 12),
  email      TEXT,           -- pre-assigned to a specific email, or NULL for open
  created_by UUID REFERENCES users(id),  -- your admin account
  used_by    UUID REFERENCES users(id),
  used_at    TIMESTAMPTZ,
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Role on users — student by default, elevated to teacher/admin explicitly
ALTER TABLE users ADD COLUMN account_type TEXT DEFAULT 'student';
-- values: 'student' | 'teacher' | 'institution_admin' | 'super_admin'
```

---

#### Backend — new file `backend/routers/institutions.py`

- [ ] `POST /api/institutions/apply` — institution submits sign-up form
  - Creates `institutions` row (plan = 'trial')
  - Creates admin `users` row with `account_type = 'institution_admin'`
  - Creates `institution_members` row (role = 'admin')
  - Sends welcome email with login link
- [ ] `GET  /api/institutions/:id` — institution admin reads their institution details
- [ ] `POST /api/institutions/:id/teachers/invite` — admin invites a teacher by email
  - Sends email with a one-time join link
  - On teacher click: creates/matches user, creates `institution_members` row (role = 'teacher'), sets `account_type = 'teacher'`
- [ ] `POST /api/institutions/:id/students/bulk` — admin bulk-imports student roster (CSV: name, email)
- [ ] `GET  /api/institutions/:id/members?role=teacher` — list teachers
- [ ] `GET  /api/institutions/:id/members?role=student` — list students
- [ ] `GET  /api/institutions/:id/overview` — cross-teacher analytics: total classrooms, total students, usage stats
- [ ] `PATCH /api/institutions/:id/members/:user_id` — suspend / reactivate a member

#### Backend — new file `backend/routers/teacher_auth.py`

- [ ] `POST /api/teacher-auth/apply` — standalone teacher applies (name, email, school name, subject)
  - Creates a pending application row (NOT a user yet — awaiting your approval)
- [ ] `POST /api/teacher-auth/redeem-invite` — teacher redeems invite code
  - Validates code exists, not used, not expired
  - Creates/matches `users` row, sets `account_type = 'teacher'`
  - Marks invite as used
  - Returns magic link or triggers email login
- [ ] Register both routers in `main.py`

#### Backend — update `backend/routers/auth.py`

- [ ] On login response, include `account_type` and `institution_id` (if member of one)
- [ ] This lets the frontend route correctly immediately after login

---

#### Frontend — Separate Teacher/Institution Portal

The student-facing site (`/auth`) stays completely unchanged.
A separate auth entry point is created for teachers and institutions.

**Option A (same domain, separate route):**
`/auth` = students (existing)
`/auth/teacher` = teachers and institutions

**Option B (separate subdomain — cleaner brand separation):**
`teach.learnx-ai.com/auth` = teacher/institution portal

Start with Option A (no infra changes). Move to Option B when you have traction.

---

#### New pages to create

**`app/auth/teacher/page.tsx` — Teacher & Institution Login Hub**

This is the landing page for all non-student accounts. Three entry points:

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│   LearnX  for  Educators                                │
│   Powerful AI tools for teachers and schools            │
│                                                          │
│   ┌──────────────────┐   ┌──────────────────────────┐  │
│   │  I have an       │   │  I represent a school    │  │
│   │  invite code     │   │  or tuition centre       │  │
│   │                  │   │                          │  │
│   │  [Enter code]    │   │  [Apply for access]      │  │
│   └──────────────────┘   └──────────────────────────┘  │
│                                                          │
│   Already have an account?  [Sign in →]                 │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**`app/auth/teacher/invite/page.tsx` — Standalone Teacher Invite Redemption**

```
┌──────────────────────────────────────────┐
│  Welcome, Teacher                        │
│                                          │
│  Enter your invite code                  │
│  [____-____-____]                        │
│                                          │
│  Your name: [________________]           │
│  Your email: [_______________]           │
│                                          │
│  [Continue →]                            │
│                                          │
│  Don't have a code? Apply for access →  │
└──────────────────────────────────────────┘
```

On submit: calls `POST /api/teacher-auth/redeem-invite` → sends magic link to email →
teacher clicks link → lands on teacher dashboard.

**`app/auth/teacher/institution/page.tsx` — Institution Sign-Up**

```
┌──────────────────────────────────────────────────────┐
│  Get LearnX for your school or centre                │
├──────────────────────────────────────────────────────┤
│  Institution name    [_________________________]     │
│  Type                [School ▼]                      │
│                      School / Tuition centre /       │
│                      University / Coaching institute │
│  Country             [Finland ▼]                     │
│  School email domain [e.g. yourschool.edu] optional  │
│                                                      │
│  Your name           [_________________________]     │
│  Your role           [Principal / IT Admin / Owner]  │
│  Your email          [_________________________]     │
│                                                      │
│  Estimated teachers  [____]                          │
│  Estimated students  [____]                          │
│                                                      │
│  [Get started — free trial →]                        │
│                                                      │
│  Free trial: up to 5 teachers, 50 students.         │
│  No credit card required.                            │
└──────────────────────────────────────────────────────┘
```

On submit: institution created in trial mode, admin account created, email sent with login.

**`app/auth/teacher/signin/page.tsx` — Teacher/Admin Sign In**

Reuses existing magic link + Google OAuth logic.
Only difference: after login, checks `account_type` and routes to:
- `account_type === 'teacher'` → `/teacher/dashboard`
- `account_type === 'institution_admin'` → `/institution/dashboard`
- `account_type === 'student'` → back to `/auth` (wrong portal — show error message)

---

#### Institution Admin Portal — new route group `app/institution/`

**`app/institution/dashboard/page.tsx`**

```
┌─────────────────────────────────────────────────────┐
│  Helsinki High School                  Trial: 3/5 teachers, 12/50 students │
├──────────────────┬──────────────────────────────────┤
│  TEACHERS  (3)   │  INSTITUTION OVERVIEW             │
│                  │                                   │
│  Ms. Patel  ✅   │  Active classrooms:  7            │
│  Mr. Smith  ✅   │  Total students:    12            │
│  Ms. Jones  ⚠️   │  Videos generated: 23            │
│  (inactive 5d)   │  AI messages:     847            │
│                  │                                   │
│  [+ Invite       │  CROSS-TEACHER SIGNALS            │
│   teacher]       │  ⚠️ Maths Unit 3 — avg 52%       │
│                  │     across 2 classes              │
├──────────────────┴──────────────────────────────────┤
│  [Invite teachers]  [Import students]  [Upgrade plan]│
└─────────────────────────────────────────────────────┘
```

**`app/institution/teachers/page.tsx`** — add/remove/suspend teachers, see their classrooms
**`app/institution/students/page.tsx`** — bulk import, list all students across institution

---

#### Login Routing Logic (centralised in `app/auth/` layout)

After any successful login, check `account_type` from the auth response and redirect:

| account_type | Redirect |
|---|---|
| `student` (default) | `/` (existing student home) |
| `teacher` | `/teacher/dashboard` |
| `institution_admin` | `/institution/dashboard` |
| `super_admin` | `/admin` (your internal admin) |

Add a link on the existing student login page:
"Are you a teacher or school? → Sign in here" pointing to `/auth/teacher`

---

#### Teacher Onboarding Flow (Standalone)

```
1. Teacher gets invite code from you (email or direct message)
2. Goes to learnx-ai.com/auth/teacher
3. Clicks "I have an invite code"
4. Enters code + name + email
5. Magic link sent to email
6. Clicks link → lands on /teacher/dashboard (empty state)
7. Guided prompt: "Create your first classroom →"
8. (Sprint 2) Upload syllabus → course extracted → publish
9. Copy join code → share with students
```

#### Institution Onboarding Flow

```
1. Principal/owner goes to learnx-ai.com/auth/teacher
2. Clicks "I represent a school or tuition centre"
3. Fills institution form (name, type, country, domain, admin details)
4. Submits → institution created in trial mode
5. Email sent: "Welcome — here's your admin login"
6. Admin logs in → /institution/dashboard (shows teacher cap: 0/5 used)
7. Admin clicks "Invite teachers" → enters teacher emails → invites sent
8. Each teacher receives email → clicks link → redeems → sets up classroom
9. Admin imports student roster CSV → students get emails with join instructions
10. Students sign up → join classrooms via code OR auto-join if email domain matches
```

**Effort: 4–5 days**

---

### Sprint 1 — Week 2: Classroom Shell

**Goal:** Teacher can create a classroom, generate a join code. Student can join.

#### Migration (`010_teacher_classrooms.sql`)

```sql
-- Distinguish teacher accounts from student accounts
ALTER TABLE users ADD COLUMN account_type TEXT DEFAULT 'student';
-- values: 'student' | 'teacher' | 'admin'

CREATE TABLE classrooms (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id  UUID REFERENCES users(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  subject     TEXT,
  grade       TEXT,
  join_code   TEXT UNIQUE NOT NULL DEFAULT substr(md5(random()::text), 1, 8),
  ai_tone     TEXT DEFAULT 'direct',  -- direct | socratic | formal
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE classroom_students (
  classroom_id UUID REFERENCES classrooms(id) ON DELETE CASCADE,
  student_id   UUID REFERENCES users(id) ON DELETE CASCADE,
  joined_at    TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (classroom_id, student_id)
);
```

#### Backend — new file `backend/routers/teacher.py`
- [ ] `POST /api/teacher/classrooms` — create, auto-generate join code
- [ ] `GET  /api/teacher/classrooms` — list teacher's classrooms
- [ ] `GET  /api/teacher/classrooms/:id/roster` — list students
- [ ] Auth middleware: reject if `account_type != 'teacher'`
- [ ] Register router in `main.py`

#### Backend — add to `backend/routers/auth.py` or new `student.py`
- [ ] `POST /api/student/classrooms/join` — look up join code, insert classroom_students row
- [ ] Role-based redirect: on login, return `account_type` in auth response so frontend routes correctly

#### Frontend
- [ ] `app/teacher/layout.tsx` — teacher shell, separate sidebar
- [ ] `app/teacher/dashboard/page.tsx` — classroom list, "Create classroom" button
- [ ] `app/teacher/classrooms/[id]/page.tsx` — show join code, empty roster
- [ ] `app/student/classrooms/page.tsx` — list classrooms the student has joined
- [ ] Login redirect logic: `account_type === 'teacher'` → `/teacher/dashboard`, else → `/` (existing)

**Effort: 3–4 days**

---

### Sprint 2 — Week 3: Course Structure + Syllabus Import

**Goal:** Teacher uploads a syllabus PDF → course structure extracted in 30 seconds → teacher reviews and publishes.
This is the "aha moment" of teacher onboarding and reuses the existing study set pipeline entirely.

#### Migration (`011_courses_units.sql`)

```sql
CREATE TABLE courses (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  classroom_id UUID REFERENCES classrooms(id) ON DELETE CASCADE,
  title        TEXT NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE units (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id   UUID REFERENCES courses(id) ON DELETE CASCADE,
  title       TEXT NOT NULL,
  order_index INT NOT NULL DEFAULT 0
);

-- Concepts reuse study_sets — just add classroom context columns
ALTER TABLE study_sets ADD COLUMN unit_id        UUID REFERENCES units(id);
ALTER TABLE study_sets ADD COLUMN order_index    INT DEFAULT 0;
ALTER TABLE study_sets ADD COLUMN is_classroom_concept BOOL DEFAULT FALSE;
ALTER TABLE study_sets ADD COLUMN unlock_at      TIMESTAMPTZ;
ALTER TABLE study_sets ADD COLUMN teacher_note   TEXT;
```

#### Backend — add to `backend/routers/teacher.py`
- [ ] `POST /api/teacher/courses` — create course attached to a classroom
- [ ] `POST /api/teacher/units` — add unit to a course, set order
- [ ] `POST /api/teacher/courses/:id/import-syllabus` — **the key endpoint:**
  - Accepts PDF upload
  - Calls existing `studyset_processor.py` concept extraction
  - Prompt updated to return grouped output: `[{unit: "Mechanics", concepts: ["Force", "Newton's Laws", ...]}, ...]`
  - Returns draft structure for teacher review — nothing saved yet
- [ ] `POST /api/teacher/courses/:id/confirm-structure` — teacher approves draft:
  - Creates `units` rows
  - Creates one `study_set` (with `is_classroom_concept=TRUE`, `unit_id` set) per concept
  - Triggers background processing on each study set using existing pipeline
- [ ] `PATCH /api/teacher/units/:id` — rename, reorder
- [ ] `DELETE /api/teacher/concepts/:id` — remove concept from course
- [ ] `GET /api/student/courses/:id` — course with units, concepts, per-student lock state

#### Frontend (Teacher)
- [ ] `app/teacher/courses/[id]/builder/page.tsx` — drag-and-drop unit + concept list
- [ ] Syllabus upload panel: upload PDF → spinner → show extracted structure → teacher edits → "Publish"
- [ ] Reuse existing `StudySetCard` component for concept cards in the builder

#### ⚠️ Known Risk
`studyset_processor.py` currently extracts concepts as a flat list.
The import-syllabus endpoint needs a **structured extraction prompt** that returns
units with grouped concepts. Estimate: half a day of prompt engineering, not code.

**Effort: 3–4 days**

---

### Sprint 3 — Week 4: Student Concept Page + Progress Tracking

**Goal:** Students can join a classroom, see the course, and work through concepts using all existing features.

#### Migration (`012_student_progress.sql`)

```sql
CREATE TABLE student_progress (
  classroom_id  UUID REFERENCES classrooms(id) ON DELETE CASCADE,
  student_id    UUID REFERENCES users(id) ON DELETE CASCADE,
  study_set_id  UUID REFERENCES study_sets(id) ON DELETE CASCADE,
  status        TEXT DEFAULT 'not_started', -- not_started | in_progress | complete
  quiz_score    INT,
  quiz_attempts INT DEFAULT 0,
  time_spent_secs INT DEFAULT 0,
  ai_chat_count INT DEFAULT 0,
  video_rewatch_count INT DEFAULT 0,
  last_seen_at  TIMESTAMPTZ,
  PRIMARY KEY (classroom_id, student_id, study_set_id)
);
```

#### Backend
- [ ] `GET /api/student/classrooms/:id/course` — course outline with per-student progress overlaid
- [ ] `PATCH /api/student/progress` — upsert on concept open / quiz complete / chat message
- [ ] Existing `studysets.py` chat, quiz, video endpoints work unchanged — concept IS a study set
- [ ] Add lock-state check to study set GET: if `unlock_at` is in future, return 403 to student

#### Frontend (Student)
- [ ] `app/student/classrooms/[id]/page.tsx` — course outline, locked/unlocked concepts
- [ ] `app/student/concepts/[id]/page.tsx` — concept page:
  - Teacher note (shown first, if set)
  - Watch video (existing `VideoStatusCard`)
  - Read PDF (existing PDF viewer)
  - Take quiz (existing quiz flow)
  - Ask AI (existing chat, scoped — Sprint 4)
  - Flag for teacher (Sprint 6)
  - Personal checklist: items tick off as student completes them

This page is the existing study set page re-skinned with a classroom context header and checklist UI.

**Effort: 2–3 days**

---

### Sprint 4 — Week 5: AI Scoping + Teacher Concept View

**Goal:** Student AI is constrained to the teacher's syllabus. Teacher sees class-wide signals per concept.

#### Backend
- [ ] Extend `studysets.py` chat: if `is_classroom_concept = TRUE`, inject classroom context:
  - Teacher name, course name, ai_tone, full concept list as boundary
  - Reuses existing `build_studyset_prompt()` — add classroom params
  - Out-of-scope response: "That's outside what we're covering — ask your teacher directly."
- [ ] Increment `student_progress.ai_chat_count` on each classroom concept chat message
- [ ] `GET /api/teacher/concepts/:id/performance` — class-wide stats: completion %, quiz avg, ai_chat_count per student
- [ ] `GET /api/teacher/students/:id` — individual student progress across all concepts in classroom

#### Frontend (Teacher)
- [ ] Teacher concept page: split view
  - Left: content editor (teacher note, attached materials)
  - Right: class performance panel — completion rate, quiz avg, top AI questions this week
- [ ] Teacher classroom roster: per-student completion %, quiz avg, last active date
- [ ] AI tone selector per classroom (Direct / Socratic / Formal) on classroom settings page

**End of Sprint 4 = shippable MVP.**
Teachers can: create classroom → import syllabus → students join → work through concepts
with scoped AI → teacher sees class performance. All existing content features work.

**Effort: 2–3 days**

---

### Post-MVP Phases (in priority order)

#### Phase 5 — Assignments + Question Bank (Weeks 6–8, ~3 weeks)

No shortcuts here — this is genuinely new.

**Migration (`013_assignments.sql`):**
```sql
CREATE TABLE questions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID REFERENCES users(id),
  study_set_id UUID REFERENCES study_sets(id),
  body TEXT NOT NULL,
  type TEXT NOT NULL,       -- mcq | short | calculation
  options JSONB,            -- [{text, correct}] for MCQ
  answer TEXT,
  explanation TEXT,
  difficulty TEXT,          -- easy | medium | hard
  marks INT DEFAULT 1,
  source TEXT DEFAULT 'teacher',  -- teacher | ai_approved
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  classroom_id UUID REFERENCES classrooms(id),
  teacher_id   UUID REFERENCES users(id),
  title TEXT NOT NULL,
  type TEXT NOT NULL,       -- quiz_retry | problem_set | reading | extra_concept
  target_type TEXT,         -- student | group
  target_id TEXT,
  study_set_id UUID REFERENCES study_sets(id),
  due_at TIMESTAMPTZ,
  teacher_note TEXT,
  config_json JSONB,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE assignment_submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id UUID REFERENCES assignments(id),
  student_id    UUID REFERENCES users(id),
  content TEXT,
  score INT,
  submitted_at TIMESTAMPTZ,
  teacher_feedback TEXT,
  reviewed_at TIMESTAMPTZ
);
```

**Checklist:**
- [ ] `POST /api/teacher/questions/generate` — AI generates batch for review
- [ ] `POST /api/teacher/questions` — save approved question to bank
- [ ] `GET  /api/teacher/questions?topic=&difficulty=&type=` — search bank
- [ ] `POST /api/teacher/assignments` — create, target student or group
- [ ] `GET  /api/student/assignments` — student's pending assignments
- [ ] `POST /api/student/assignments/:id/submit`
- [ ] `PATCH /api/teacher/assignments/:id/submissions/:sid` — leave feedback
- [ ] Question builder UI: write / AI-generate-and-approve / mix modes
- [ ] Question bank page: filter, search, select for assignment
- [ ] Assignment creator UI: type picker, target picker, due date, attach questions
- [ ] Student assignment list + submission page with scoped AI

---

#### Phase 6 — Individual Tracking + Needs Attention (Weeks 9–10, ~2 weeks)

Reads from `student_progress` data that has been accumulating since Sprint 3.

**Checklist:**
- [ ] `GET /api/teacher/classrooms/:id/performance` — full per-student signal matrix
- [ ] Background job (hourly): detect signals, write to `attention_signals` table
  - Quiz failed 3× → signal
  - No activity 5+ days → signal
  - Score dropped 20%+ → signal
  - AI chat spike on concept → signal
- [ ] `GET /api/teacher/classrooms/:id/attention-queue`
- [ ] `PATCH /api/teacher/signals/:id/resolve`
- [ ] Student profile page: progress, behaviour signals, AI chat summary, one-click actions
- [ ] Attention queue widget on teacher dashboard
- [ ] Class performance heatmap (concept × student grid, colour by score)

---

#### Phase 7 — Student Grouping (Week 11, ~1 week)

Depends on tracking data existing first.

```sql
CREATE TABLE student_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  classroom_id UUID REFERENCES classrooms(id),
  name TEXT NOT NULL,
  type TEXT NOT NULL,     -- manual | dynamic
  rule_json JSONB,        -- {field, operator, value} for dynamic groups
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE student_group_members (
  group_id   UUID REFERENCES student_groups(id) ON DELETE CASCADE,
  student_id UUID REFERENCES users(id) ON DELETE CASCADE,
  added_at   TIMESTAMPTZ DEFAULT NOW(),
  added_by   TEXT,        -- teacher | auto
  PRIMARY KEY (group_id, student_id)
);
```

- [ ] Manual group creator (drag students in)
- [ ] Dynamic group rule builder (field + operator + value)
- [ ] Hourly job: re-evaluate dynamic group membership
- [ ] Assignments can target a group_id

---

#### Phase 8 — Custom Content Creation (Weeks 12–13, ~2 weeks)

Script editor, image upload with AI improvement, teacher video upload + transcription.

```sql
ALTER TABLE study_sets ADD COLUMN script_teacher TEXT;  -- teacher's raw notes
ALTER TABLE study_sets ADD COLUMN script_final   TEXT;  -- approved version

CREATE TABLE concept_images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  study_set_id UUID REFERENCES study_sets(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  caption TEXT,
  ai_description TEXT,
  teacher_approved BOOL DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE concept_videos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  study_set_id UUID REFERENCES study_sets(id) ON DELETE CASCADE,
  source TEXT NOT NULL,   -- manim | teacher_upload | script
  video_url TEXT,
  transcript TEXT,
  chapter_markers JSONB,
  duration_secs INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] `POST /api/teacher/concepts/:id/images` — upload, trigger AI caption + description
- [ ] `POST /api/teacher/concepts/:id/script/improve` — AI improvement (mode: polish/expand/simplify/structure)
- [ ] `POST /api/teacher/concepts/:id/script/generate-video` — feed script to existing Manim pipeline
- [ ] `POST /api/teacher/concepts/:id/videos/upload` — multipart to R2
- [ ] Background job: Whisper transcription → chapter markers → store on `concept_videos`
- [ ] Script editor with AI improvement panel + side-by-side diff UI
- [ ] Image uploader with caption diff view
- [ ] Teacher video upload with transcript review + chapter editor

---

#### Phase 9 — Teacher ↔ Student Interaction (Weeks 14–15, ~2 weeks)

```sql
CREATE TABLE teacher_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  study_set_id  UUID REFERENCES study_sets(id),
  assignment_id UUID REFERENCES assignments(id),
  teacher_id    UUID REFERENCES users(id),
  student_id    UUID REFERENCES users(id),  -- NULL = visible to whole class
  body TEXT,
  voice_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE student_flags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  study_set_id UUID REFERENCES study_sets(id),
  student_id   UUID REFERENCES users(id),
  message TEXT NOT NULL,
  resolved     BOOL DEFAULT FALSE,
  resolved_at  TIMESTAMPTZ,
  teacher_reply TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] Teacher leaves text/voice comment on a concept or assignment
- [ ] Student flags a concept or AI response for teacher review
- [ ] Teacher flags inbox: filter by concept/student, one-click resolve with reply
- [ ] Browser + email push notification on: new flag, teacher reply, new comment
- [ ] "Message from teacher" badge on student concept card

---

#### Phase 10 — Live Sessions (Weeks 16–17, ~2 weeks)

Lowest immediate ROI — implement last.

- [ ] Session create/start/end management
- [ ] Student join flow (push notification → join link)
- [ ] Student question queue during session
- [ ] Auto-record session, attach recording to concept after end

---

## Teacher Onboarding Flow

Student onboarding is frictionless (sign up → profile → chat in 60 seconds).
Teacher onboarding is trust-first and setup-before-value.

```
Student                          Teacher
───────────────────────────────  ───────────────────────────────
Sign up                          Get invite code (early: manual;
                                 later: school email domain auto-verify)
↓                                ↓
Profile: grade + goal (2 Q's)   Set account_type = 'teacher'
↓                                ↓
Chat immediately                 Create classroom (name, subject, grade)
                                 ↓
                                 Upload syllabus PDF
                                 ↓
                                 Review AI-extracted course (30 seconds)
                                 — drag to reorder, rename, delete concepts
                                 ↓
                                 Generate first video + quiz for one concept
                                 ↓
                                 Preview student view (role-switch button)
                                 ↓
                                 Copy join code → invite students
                                 ↓
                                 Students join → classroom live
```

**Verification strategy by stage:**
- Beta launch: invite-only (issue teacher codes manually)
- Early growth: school email domain check (`@school.edu`, `@edu.fi`)
- Scale: self-serve with manual review queue for non-school emails

---

## Full Timeline Summary

| Sprint / Phase | Week | Deliverable | New vs Reused |
|---|---|---|---|
| Sprint 0 | 1 | Institutions + teacher accounts + separate auth portal | New: institutions tables, invite system, `/auth/teacher` portal, institution admin dashboard |
| Sprint 1 | 2 | Classroom CRUD + join flow | New: teacher router, classroom tables, teacher dashboard |
| Sprint 2 | 3 | Course builder + syllabus import | New: courses/units tables, import UI. **Reused: entire study set pipeline** |
| Sprint 3 | 4 | Student concept page + progress tracking | New: progress table, student course view. **Reused: study set page, quiz, chat, video** |
| Sprint 4 | 5 | AI scoping + teacher concept view | New: classroom context in system prompt, perf endpoint. **Reused: prompt_builder.py** |
| **← MVP complete** | | | |
| Phase 5 | 6–8 | Assignments + question bank | Mostly new |
| Phase 6 | 9–10 | Individual tracking + attention queue | Reads from existing progress data |
| Phase 7 | 11 | Student grouping | Depends on Phase 6 data |
| Phase 8 | 12–13 | Custom content (script, image, video upload) | New: upload + transcription. Reused: Manim pipeline |
| Phase 9 | 14–15 | Teacher ↔ student interaction | New |
| Phase 10 | 16–17 | Live sessions | New |

**MVP (Sprint 0–4): 5 weeks solo.**
**Full platform: ~17 weeks solo, ~9–10 weeks with a 2-person team.**

Sprint 0 (institutions + separate auth portal) adds 1 week but is non-negotiable —
without it there is no safe, scalable way to onboard teachers or schools.
The syllabus import + study set reuse still saves ~6 weeks vs building content infrastructure from scratch.

---

## Auth Portal Summary

| URL | Who uses it | What it does |
|---|---|---|
| `/auth` | Students | Existing login — unchanged |
| `/auth/teacher` | Teachers + admins | Hub: invite code redemption OR institution sign-up OR sign in |
| `/auth/teacher/invite` | Standalone teachers | Redeem invite code → magic link → teacher dashboard |
| `/auth/teacher/institution` | School/centre admins | Institution sign-up form → trial account created |
| `/auth/teacher/signin` | Returning teachers/admins | Magic link or Google → routed by account_type |
| `/teacher/dashboard` | Teachers | Classroom management |
| `/institution/dashboard` | Institution admins | Cross-teacher overview, member management |
