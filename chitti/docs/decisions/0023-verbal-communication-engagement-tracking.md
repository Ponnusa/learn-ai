# 0023 — Verbal-communication engagement tracking (behavioral, not evaluative)

Date: 2026-10-15
Status: Accepted

## Context

A series of design discussions explored whether Chitti should grade
correctness in English/Finnish (a deterministic evaluation engine,
mirroring the one proposed for math). That direction was rejected: no
deterministic evaluator exists for grammar or pronunciation, and
building one is a research project, not a feature. The goal was
reframed instead around a real, more tractable problem: some children
are hesitant to speak at all, and a patient, non-judgmental practice
partner that's always available could plausibly help with that --
without needing to judge whether anything said was "right."

That reframe turns the problem from evaluative (hard, unsolved) to
behavioral (easy, measurable): did the child talk, how much, how
often. This decision implements the smallest possible slice to test
whether tracking that is worth building further.

## What this is, and isn't

- **Is**: plain counting -- turns taken and words spoken per session,
  written once at session end, surfaced to the parent.
- **Isn't**: any kind of correctness or proficiency evaluation, any
  LLM involvement in computing or interpreting the numbers, anything
  spoken back to the child as a score (that would risk making the
  interaction feel like a test, which cuts against the whole point).
  No cross-subject or curriculum tracking either -- this stays scoped
  to Teachable-Friend and Story Companion as they exist today.

## Implementation

New `engagement/` package (`schema.py`'s `EngagementSession`/
`EngagementMode`, `repository.py`'s `EngagementRepository`), same
shape as the existing `reminders/` and `memory/` domain packages --
`__init__(conn)` runs the shared migrations, `create()`/
`list_for_child()`/`latest_for_child()`. New `engagement_sessions`
table registered in `storage/migrations.py`.

`voice_loop_demo.py`'s `_record_engagement_session()` counts child
turns/words from the same `messages` list `_summarize_and_remember_
session()` already uses, called from the same `finally` block in both
`_run_teachable_friend()` and `_run_story_companion()` -- no new
crash-resilience work needed since it's a single synchronous insert,
not an LLM call (decision 0021's cancellation handling doesn't apply
here).

`parent_controls/app.py` gained a read-only `/profiles/<id>/
engagement` route and `engagement.html` template, linked from
`profiles.html` next to the existing memories link -- the parent sees
turn/word counts per session, the same way they already see memory
records.

## Consequences

9 new unit tests (126 total passing): `EngagementRepository`'s
create/list/scoping/latest-for-child behavior, `_record_engagement_
session()` counting only child turns and skipping an all-assistant
session, and the new Flask route rendering correctly with and without
data.

## Not yet done

No comparison-to-last-time logic is spoken or shown anywhere yet
(deliberately deferred -- the numbers exist now so that decision can
be made with real data instead of guessing). No Finnish-specific
handling (still blocked on decision 0020's English-only STT). Whether
this actually helps a hesitant child, and whether richer signals
(response latency, self-initiated turns) are worth adding, is an open
question this data collection is meant to help answer, not something
this decision claims to have solved.
