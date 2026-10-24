# 0108 — Only speak the welcome-back recap once per day

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback from real use:

> "each time when i login to pi, start the voice demo, it passes the
> start transcript so it can give a welcome message. most probably
> this needent happen each time, it muts be only for the start if
> day, after that ut must be cahced and used, so we dont speak the
> same again agian and reduce ai calls"

Confirmed in `voice_loop_demo.py`: every time the demo starts,
`_maybe_greet_with_recap()` runs unconditionally (decision 0018) --
if a `DAILY_SUMMARY` memory exists, it calls
`conversation.welcome_back_greeting()` (an LLM call) and speaks the
result. SSHing in and restarting the demo several times in one day
(exactly what happens during real use/debugging on the Pi) re-ran
that LLM call every single time, for a recap that hadn't changed
since the last restart that same day -- a real, avoidable
contributor to API call volume, same spirit as decision 0102's own
TTS disk cache.

## What shipped

**`parent_controls/profiles.py`**: `ChildProfile` gains
`last_greeted_date: str = ""` (ISO date string, device-local, not
UTC -- this runs on the Pi itself, not a server spanning timezones,
so the Pi's own clock already matches the household's actual day).
New `ChildProfileRepository.mark_greeted(profile_id, date_str)` -- a
narrow, purpose-built write, not routed through `update()`'s
parent-facing field list, which has nothing to do with this
bookkeeping.

**`storage/migrations.py`**: `_ensure_column()` call adding
`last_greeted_date TEXT NOT NULL DEFAULT ''` to `child_profiles`,
same pattern every other column added after the table already
existed on the Pi (speech_speed, interest, preferred_phase, ...).

**`voice_loop_demo.py`**: `_maybe_greet_with_recap()` now takes the
`ChildProfileRepository` too, checks `profile.last_greeted_date ==
date.today().isoformat()` first and returns immediately if so --
before even looking at `DAILY_SUMMARY` memories, let alone calling
the LLM. After actually speaking a greeting, calls
`profiles.mark_greeted(profile.id, today)` so the next restart that
same day skips it.

**Deliberately just silence, not a replayed cached line**: re-reading
the request, "cached and used ... so we don't speak the same again"
reads as wanting the *fact that a greeting already happened today*
remembered (so it isn't redone), not a recorded audio clip replayed
on every subsequent restart. Speaking the same recap sentence
multiple times a day to the same child seemed more likely to feel
odd than reassuring, so a repeat restart now just goes straight into
the session with no greeting at all -- the same "silently does
nothing" shape decision 0018 already uses for the very-first-session
case.

## Consequences

Two new tests in `test_voice_loop_demo_memory.py` (skips entirely --
no LLM call, no TTS, no audio -- when already greeted today; marks
the profile greeted after actually speaking). The three existing
greet tests now also pass a `ChildProfileRepository` and a persisted
profile. Four new tests in `test_child_profile_last_greeted.py`
(default empty; `mark_greeted` sets the date; leaves other fields
alone; no-ops for an unknown profile id). One assertion added to
`test_migrations_ensure_column.py`'s existing end-to-end check.

Full suite: 686 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

No parent-facing control to force a re-greet on the same day (e.g.
after a long gap mid-day) -- not asked for, and the existing
first-session silent-skip precedent suggests it isn't needed; a
natural, separable follow-up if it ever comes up in practice.
