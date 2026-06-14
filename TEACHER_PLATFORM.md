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

### Phase 1 — Foundation (Weeks 1–4)

**Goal:** Teachers can build a course and students can follow it.

#### Backend
- [ ] DB migrations: `classrooms`, `classroom_students`, `courses`, `units`, `concepts`
- [ ] `POST /api/teacher/classrooms` — create classroom, generate join code
- [ ] `POST /api/teacher/classrooms/:id/students` — bulk add / invite students
- [ ] `GET  /api/teacher/classrooms/:id/roster` — list students
- [ ] `POST /api/teacher/courses` — create course with units and concepts
- [ ] `PATCH /api/teacher/concepts/:id` — update concept content, unlock rules
- [ ] `POST /api/student/classrooms/join` — student joins via code
- [ ] `GET  /api/student/courses/:id` — student gets course with lock/unlock state
- [ ] `PATCH /api/student/progress` — upsert student_progress on concept open/complete

#### Frontend (Teacher)
- [ ] `/teacher/dashboard` — classroom list, create classroom flow
- [ ] `/teacher/classrooms/:id/roster` — student list, invite/remove
- [ ] `/teacher/courses/:id/builder` — drag-and-drop unit + concept builder
- [ ] `/teacher/concepts/:id/edit` — concept content editor (text, note, unlock settings)

#### Frontend (Student)
- [ ] `/student/classrooms` — list of joined classrooms
- [ ] `/student/courses/:id` — course outline, locked/unlocked state
- [ ] `/student/concepts/:id` — concept page (checklist view)

---

### Phase 2 — Content Creation (Weeks 5–8)

**Goal:** Teachers can upload and create rich content per concept; AI assists.

#### Backend
- [ ] DB migrations: `concept_images`, `concept_videos`, update `concepts` for script fields
- [ ] `POST /api/teacher/concepts/:id/images` — upload image to R2, trigger AI caption
- [ ] `POST /api/teacher/concepts/:id/script/improve` — AI improvement (mode param)
- [ ] `POST /api/teacher/concepts/:id/script/generate-video` — feed script to Manim pipeline
- [ ] `POST /api/teacher/concepts/:id/videos/upload` — multipart video upload to R2
- [ ] Background job: Whisper transcription after video upload → store transcript + chapter markers
- [ ] `PATCH /api/teacher/concepts/:id/videos/:vid/transcript` — teacher edits transcript

#### Frontend (Teacher)
- [ ] Image uploader in concept editor — drag/drop, AI caption panel, diff view
- [ ] Script editor with AI improvement panel — mode picker, side-by-side diff, accept/reject
- [ ] "Generate video from script" — triggers existing Manim flow with teacher script as narration
- [ ] Video uploader — progress bar, transcript review panel, chapter marker editor

---

### Phase 3 — Assignments & Question Bank (Weeks 9–12)

**Goal:** Teachers can assign work to students and groups; question bank grows over time.

#### Backend
- [ ] DB migrations: `questions`, `assignments`, `assignment_submissions`, `student_groups`, `student_group_members`
- [ ] `POST /api/teacher/questions/generate` — AI generates batch, returns for review
- [ ] `POST /api/teacher/questions` — save approved question to bank
- [ ] `GET  /api/teacher/questions?topic=&difficulty=` — search question bank
- [ ] `POST /api/teacher/assignments` — create assignment, target student or group
- [ ] `GET  /api/student/assignments` — student sees their pending assignments
- [ ] `POST /api/student/assignments/:id/submit` — submit assignment
- [ ] `PATCH /api/teacher/assignments/:id/submissions/:sid` — teacher leaves feedback
- [ ] `POST /api/teacher/groups` — create manual group
- [ ] `POST /api/teacher/groups/dynamic` — create rule-based group, evaluate immediately

#### Frontend (Teacher)
- [ ] Question builder — write/AI generate/mix modes, per-question approve/edit/reject/regen UI
- [ ] Question bank page — filter, search, select for assignment
- [ ] Assignment creator — pick type, target student or group, set due date, attach questions
- [ ] Group manager — create manual groups, set dynamic rules, see current members

#### Frontend (Student)
- [ ] "My Assignments" tab — list with due dates, status
- [ ] Assignment detail page — work through questions with scoped AI, submit

---

### Phase 4 — AI Scoping & Student Chat (Weeks 13–14)

**Goal:** Student AI is constrained to teacher's syllabus; teacher can see chat.

#### Backend
- [ ] Build `concept_knowledge_base` at query time: script_final + image descriptions + video transcript
- [ ] New chat endpoint `/api/student/chat` — system prompt includes syllabus boundary + knowledge base
- [ ] `GET /api/teacher/concepts/:id/chat-logs?student_id=` — teacher reads student AI transcripts
- [ ] AI chat volume aggregated in student_progress on each message

#### Frontend
- [ ] Student concept page: "Ask AI about this concept" → opens scoped chat, not global chat
- [ ] Teacher concept page: "Student questions" panel showing AI chat patterns and top questions
- [ ] Teacher settings per concept: set AI tone (Direct / Socratic / Formal)

---

### Phase 5 — Individual Tracking & Needs Attention (Weeks 15–17)

**Goal:** Teachers see who is struggling and can act in one click.

#### Backend
- [ ] Aggregate view: `GET /api/teacher/classrooms/:id/performance` — per-student signals
- [ ] Signal detector (background job, runs hourly):
  - Quiz failed 3+ times → create attention_signal
  - No activity 5+ days → create attention_signal
  - Score dropped 20%+ → create attention_signal
  - AI chat spike on a concept → create attention_signal
- [ ] `GET /api/teacher/classrooms/:id/attention-queue` — active unresolved signals
- [ ] `PATCH /api/teacher/signals/:id/resolve` — mark signal handled

#### Frontend (Teacher)
- [ ] Student profile page — progress, behaviour signals, AI chat summary, one-click actions
- [ ] Attention queue widget on dashboard — cards per signal, inline actions
- [ ] Class performance heatmap — concept × student grid, colour by score or completion

---

### Phase 6 — Teacher ↔ Student Interaction (Weeks 18–20)

**Goal:** Async communication anchored to specific content.

#### Backend
- [ ] DB migrations: `teacher_comments`, `student_flags`
- [ ] `POST /api/teacher/concepts/:id/comments` — text or voice note (voice stored in R2)
- [ ] `POST /api/student/concepts/:id/flags` — student raises a flag
- [ ] `GET  /api/teacher/classrooms/:id/flags` — teacher sees all open flags
- [ ] `PATCH /api/teacher/flags/:id` — teacher resolves flag with reply
- [ ] Push notifications (browser + email) for: new flag, teacher reply, new comment

#### Frontend (Teacher)
- [ ] Comment panel on concept page — add text/voice, see student replies, resolve flags
- [ ] Flags inbox — list of open flags, filter by concept or student, one-click resolve

#### Frontend (Student)
- [ ] "Message from teacher" badge on concept card
- [ ] Flag button on concept page and on individual AI messages
- [ ] Notification bell: teacher replied to flag / new comment

---

### Phase 7 — Live Sessions (Weeks 21–22)

**Goal:** Real-time teacher-led sessions attached to concepts.

#### Backend
- [ ] Session management: start/end session, student join tracking
- [ ] Question queue: students submit text questions during session
- [ ] Auto-record session, store video, attach to concept after session ends

#### Frontend
- [ ] Teacher: "Go Live" button on any concept, question queue panel
- [ ] Student: join notification, question submission input, live video embed

---

## Summary Checklist

| Phase | Weeks | Deliverable |
|---|---|---|
| 1 | 1–4 | Classrooms, roster, course builder, student concept page |
| 2 | 5–8 | Image upload, script editor + AI improve, teacher video + transcription |
| 3 | 9–12 | Question bank, assignment builder, groups, student submissions |
| 4 | 13–14 | Scoped student AI chat, teacher chat visibility |
| 5 | 15–17 | Individual tracking, attention queue, performance heatmap |
| 6 | 18–20 | Teacher comments, student flags, notifications |
| 7 | 21–22 | Live sessions, recording, question queue |

**Total estimated build: ~22 weeks for a solo developer, ~10–12 weeks with a 2-person team.**

Phase 1–4 is the core MVP — classrooms, content, assignments, and scoped AI. That alone is a shippable product.
