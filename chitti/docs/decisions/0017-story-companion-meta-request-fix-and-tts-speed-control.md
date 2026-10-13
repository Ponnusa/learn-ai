# 0017 — Story Companion meta-request fix, parent-controlled TTS speed

Date: 2026-10-13
Status: Accepted

## Context

Follow-up from the first real Story Companion session (decision
0016's live testing). Two things came out of reviewing that
transcript: an over-strict grounding response to a benign meta-request,
and real-world feedback that the default speech pace reads too fast
for a child to follow comfortably.

## Story Companion fix: "say the story in English" → "I'm not sure"

A real exchange asked Chitti to retell its own story in English, and
got "I'm not sure" back. Root cause: `build_story_companion_prompt()`'s
"if the answer isn't actually in the story, say you're not sure rather
than guessing" instruction — correct for preventing fabricated story
facts (the thing decision 0003's risk #3c was worried about, now
confirmed working well: a factual question, "what was the hedgehog's
name," got answered correctly and concisely) — was over-applied to a
request that isn't a factual question at all. Retelling, summarizing,
or translating content the model already generated introduces no new,
unverified facts.

**Fix**: the prompt now explicitly scopes the caution to story facts
and separately carves out retelling/summarizing/translating as always
fine. No code change beyond the prompt string; existing tests still
pass unchanged.

## Parent-controlled TTS speech speed

Reported live: replies read too fast to follow. OpenAI's TTS API has
a built-in `speed` parameter (0.25–4.0, default 1.0). Decision: put
the control with the **parent**, not a child voice command — consistent
with how age and feature toggles already live on `ChildProfile`, and
avoids adding an unvalidated "talk slower" voice-command surface a
child could invoke to change device behavior.

- `TextToSpeechBackend.synthesize()`'s interface gained an optional
  `speed: float = 1.0` parameter; `OpenAITTSBackend` passes it straight
  through to OpenAI's API, letting an out-of-range value surface as a
  clear API error rather than silently clamping it.
- `ChildProfile` gained `speech_speed: float = 1.0`.
- New Parent Controls route, `/profiles/<id>/edit` (previously
  profiles could only be created or deleted, never edited at all) —
  validates the 0.25–4.0 range in-page before it ever reaches the API.
- `voice_loop_demo.py` reads the demo profile's `speech_speed` and
  threads it through every `_speak()` call in both modes.

## A real schema-evolution gap, found and fixed before it could bite

`child_profiles` already exists as a live table on the Pi (created
during earlier testing, before `speech_speed` existed). This project's
migration system so far has only ever used `CREATE TABLE IF NOT
EXISTS` — which is a **no-op for a table that already exists**, so
simply adding the column to the `CREATE TABLE` statement would have
silently done nothing on that already-created database; the app would
have crashed with "no such column: speech_speed" the next time
anything touched it on the Pi.

Caught before it reached real hardware this time, by reasoning through
what "idempotent" actually covers rather than assuming the existing
docstring's claim. **Fix**: `storage/migrations.py` gained
`_ensure_column()` — checks `PRAGMA table_info` and runs an explicit
`ALTER TABLE ... ADD COLUMN` only if the column is actually missing,
safe to call on both a brand-new database and an already-existing one.
3 new tests cover exactly this: a simulated pre-existing table missing
the column, a no-op second call, and the full `run_migrations()` path
against a table shaped like the one already live on the Pi.

## Consequences

10 new unit tests (99 total passing): the schema-migration scenario
above, `speech_speed` create/update round-trips, a custom-speed TTS
request, and the new edit-profile route (including rejecting an
out-of-range value). `docs/decisions/0003`'s risk #3c is now closer to
resolved — Story Companion's grounding behavior is confirmed working
on a real model, with one real gap found and fixed.
