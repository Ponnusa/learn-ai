# 0053 — Reading Partner teleprompter display

Date: 2026-10-18
Status: Accepted

## Context

Decision 0052's hint-and-retry loop shipped with a real bug, confirmed
live on the Pi: when Chitti hints on a missed word, it never says or
shows *which* word it means -- the screen had already gone back to
the plain face (`face.set_reading_text(None)` fires right after the
read-aloud capture, before grading/hinting even starts). The product
owner's fix idea went further than patching that one bug: highlight
each word as the child is meant to read it, at a parent-configurable
pace, grade the whole read with the existing deterministic miscue
engine (not an LLM -- `assess()` already does exactly this, more
reliably and for free), and show wrong/missed words distinctly so the
child can practice them. Confirmed via AskUserQuestion: when hinting,
the display should *freeze* on just the missed word rather than try
to highlight it inline while a scroll continues.

Also requested: parent-configurable pace, font size, and font color,
and a bottom-to-top teleprompter scroll specifically so a longer
passage (a parent-uploaded exercise, decision 0052) is never silently
cut off the way the old `_draw_reading_text()`'s overflow guard did.

**Honesty check, carried over from decision 0052**: the scroll is a
*pacing aid*, not reactive to the child's actual speech. Chitti's mic
capture is push-to-talk (record the whole read, transcribe once), with
no live/streaming recognition, so there's no way to detect "has the
child actually finished saying this word yet." The highlight advances
on a timer at the parent-configured pace regardless of whether the
child is keeping up.

## What shipped

**Parent-configurable pace/size/color** (`parent_controls/profiles.py`):
three new `ChildProfile` fields -- `reading_pace_wpm` (default 45.0),
`reading_font_size` (default 28, matching the old hardcoded constant),
`reading_font_color` (default `"white"`). Color is a short vetted list
(`white`/`yellow`/`cyan`/`green`, all legible against the display's
dark background) rather than a free picker, so a parent can't
accidentally choose something unreadable. New fields on
`edit_profile.html`, validated in `app.py`'s `edit_profile()` (pace
20-120 wpm, size 18-48px, color against the list) with the same
"clear in-page error" style `speech_speed`'s validation already uses.
Migrated via three more `_ensure_column()` calls, same pattern
`speech_speed`/`interest` already used.

**Word-timeline + scrolling teleprompter** (`device/screen_face.py`):
`_build_word_timeline()` wraps a book's pages into screen lines
(reusing the existing `_wrap_text()`) and assigns every word an equal
`60/wpm`-second slot in reading order; each `TimedWord` tracks its own
line and *character span within that line* (not just its text), so a
repeated word like "the" highlights the correct occurrence, not
always the first. `_current_word_index()` finds the word whose window
contains the elapsed time, holding on the last word once the total
duration has passed -- never loops, never goes blank, so every line
gets its moment regardless of how long the child actually takes.
`_draw_teleprompter()` anchors the *current* line at the screen's
vertical middle and offsets every other line by its distance in
lines -- read lines scroll up and off the top, upcoming lines queue in
from the bottom, and anything outside the visible band simply isn't
drawn. This replaces the old `_draw_reading_text()`, whose overflow
guard silently cut off anything that didn't fit; nothing is ever lost
now, it just hasn't scrolled into view yet.

`set_reading_text()` gained `wpm`/`font_size`/`font_color` keyword
parameters and now stamps an internal start time used to compute
elapsed time each frame; fonts are created on demand and cached by
size in the render thread (font size is no longer one fixed module-
level constant). The word timeline itself is only rebuilt when the
underlying lines/size/pace actually change, not every frame.

**Frozen word spotlight for hints** -- the actual bug fix: a new,
independent `set_reading_spotlight(word)` draws *only* that word,
large and centered, in red, skipping the teleprompter and the face
entirely while it's set. `_run_reading_partner()` calls it once before
the hint loop's first stage and clears it once the loop ends (success
or exhausted) -- the child now always sees which word is being asked
about throughout all three stages, while the *spoken* hint content
still escalates from vague encouragement to the full word exactly as
decision 0052 already built.

**Wiring**: `face.set_reading_text(book.pages, wpm=..., font_size=...,
font_color=...)` moved to right before the read-aloud capture (after
the spoken intro, not before it), so the teleprompter's clock starts
close to when the child is actually expected to begin reading rather
than burning scroll time while Chitti is still talking. Exact sync
with the real Enter-press moment isn't attempted -- an inherent
push-to-talk limitation, not something this decision tries to solve.

## Consequences

Pure-function tests for `_build_word_timeline()`/`_current_word_index()`
in `test_screen_face.py`, using a small duck-typed fake font (no
pygame import needed, same split `_wrap_text()`/`_resolve_expression()`
already use) -- including a dedicated test for the repeated-word
char-span case and the hold-past-total-duration behavior. New
`set_reading_text()`/`set_reading_spotlight()` lock/getter tests in
the same file, a pygame-gated render-thread smoke test in
`test_screen_face_rendering.py`, a new `test_child_profile_reading_display.py`
for the three profile fields, new `app.py` route/validation tests, and
extended end-to-end `_run_reading_partner()` tests asserting the
spotlight is set before hinting and cleared after. Full suite: 421
passed, 1 skipped (pygame not installed in this dev environment,
pre-existing per decision 0040).

## Not yet done

- Punctuation-aware pacing (a pause at commas/periods) -- uniform
  per-word duration only.
- True speech-synced highlighting -- needs streaming STT/VAD, which
  Chitti doesn't have (the same constraint decision 0052 already
  documented). Tracked as its own future feasibility evaluation in
  decision 0004's "Open follow-ups" (2026-10-18 entry) -- a real
  architecture decision, not a quick add-on, since it needs a
  different STT backend and changes to both the audio capture layer
  and this decision's render loop.
- Per-word-length pace scaling -- uniform `seconds_per_word` only.
- A free color picker -- the vetted list stays fixed.
