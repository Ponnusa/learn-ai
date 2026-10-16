# 0038 — Conversation transcripts for parent transparency + Parent Controls redesign

Date: 2026-10-16
Status: Accepted

## Context

Requested directly: parents should be able to see exactly what was
said in a session, not just a curated summary -- and the Parent
Controls web UI should look better (it was plain, unstyled HTML).

**This knowingly narrows a documented Milestone-0 privacy decision,
and that needs to be said plainly, not built around quietly.**
`docs/privacy_data_map.md` states: *"Conversation context —
temporary, in-memory only for the duration of a session. Never
persisted as a durable memory record."* `memory/schema.py`'s
`MemoryCategory.CONVERSATION_CONTEXT` is walled off specifically to
enforce this -- `MemoryRepository.create()` raises `ValueError` for
it (decision 0007), with a test asserting the rejection. That same
document also says plainly: *"No DPIA (Data Protection Impact
Assessment) has been performed... required before any child-facing
pilot, with specialist privacy advice."* Persisting full transcripts
is exactly the kind of decision a DPIA exists to evaluate, and none
has happened.

This decision does **not** reopen decision 0007 or weaken
`MemoryRecord`'s invariant -- `CONVERSATION_CONTEXT` stays correctly
walled off from `MemoryRepository`, and its rejection test is
unchanged. Instead, conversation transcripts are a **separate,
explicitly-governed feature**, modeled on `MemoryRecord`'s shape
(consent status, retention policy, expiry) rather than bypassing that
model, so the narrowing of the original privacy statement is visible
and auditable in its own right.

## What shipped

**Part 1 — transcript persistence.** New `transcripts/` package
(`TranscriptRecord`/`TranscriptRepository`, same shape as `engagement/`
and `memory/`): `child_profile_id`, `mode` (reuses `EngagementMode`,
not a duplicate enum), `content` (the session's full `"role:
content"` lines -- reusing the exact format `_summarize_and_
remember_session()` already builds, no new formatting logic),
`consent_or_authorization_status`, `retention_policy`, and
`expires_at`, defaulted to 90 days from creation
(`_TRANSCRIPT_RETENTION_DAYS` in `voice_loop_demo.py`). New
`_save_transcript()` helper, called in the same `finally` block as
the existing `_summarize_and_remember_session()`/`_record_engagement_
session()` calls, in all three modes. A new `/profiles/<id>/
transcripts` Parent Controls page (list + delete, same pattern as
the existing memories page) renders each session with speaker lines
visually distinguished.

**Part 2 — visual redesign.** No styling existed at all (no `<link>`,
no `<style>`, no `static/` folder, just two inline `style="..."`
attributes). New `static/style.css` (plain CSS, no framework, no
build step -- this stays a small server-rendered Flask app) gives a
calm, trustworthy look (parents' UI, not the child-facing voice) --
card-style lists, consistent buttons (a distinct "danger" style for
delete actions), styled forms and tables, and a persistent header/nav
replacing the old "Back"-link-only navigation. All 9 templates got
light markup updates (classes only, not rewrites) plus empty-state
messages where a list could previously render silently empty.

## Consequences

16 new unit tests (239 total passing): `TranscriptRepository`'s
create/list/scoping/expiry/purge behavior (mirroring `memory/
repository.py`'s own expiry-as-deletion test pattern), `_save_
transcript()`'s formatting and empty-session guard, and the new
Parent Controls route's list/delete/empty-state behavior. The visual
redesign has no automated test (consistent with this project's
stance that visual judgment calls aren't asserted in Python) --
verified instead with a live Flask-test-client smoke test across
every route, confirming clean rendering, correct speaker styling, and
working empty states, before writing the formal tests.

`docs/privacy_data_map.md`'s conversation-context line is updated to
point here rather than leave the original blanket statement looking
contradicted.

## Not yet done

No DPIA has been performed -- unchanged, pre-existing gap, not
resolved by this decision. No scheduled retention enforcement exists
-- `TranscriptRepository.purge_expired()` exists and is tested, but
nothing calls it on a schedule, the same honest gap `MemoryRepository.
purge_expired()` already has. The 90-day default retention is a
label applied at write time, not yet an enforced guarantee.
