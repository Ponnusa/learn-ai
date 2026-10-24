# 0105 — A nicer starting-phase picker in Parent Controls

Date: 2026-10-24
Status: Accepted

## Context

Direct follow-up to decision 0104: the "Starting phase" control it
shipped was a bare `<select>` with each phase's title and subtitle
crammed into one dropdown-option line -- functional, but not
"nicely" presented, and `style.css` (plain CSS, no framework by this
project's own stated design) has no styling for `<select>` at all,
so it looked visually inconsistent with the rest of the form's
styled inputs.

## What shipped

**`parent_controls/templates/edit_profile.html`**: the `<select>`
replaced with a `<fieldset class="phase-picker">` of radio-button
"cards" -- one per phase (plus "No preference"), each showing its
title and subtitle on their own lines, not squeezed into one option
string. Same `name="preferred_phase"`/`value`s as before, so the
backend parsing in `app.py` needed no change at all.

**`parent_controls/static/style.css`**: new `.phase-card` rules,
reusing this file's own existing `--surface`/`--border`/`--radius`/
`--accent` tokens (the same look `card-list` already establishes
elsewhere in this app) rather than inventing a new visual language.
The selected card highlights via `:has(input:checked)` -- plain CSS,
no JavaScript, consistent with this project's explicit "no build
step, no framework" choice for this UI.

Verified against the real running app, not just the unit tests:
started the Flask dev server, drove the real PIN-setup -> login ->
create-profile -> edit-profile flow with `curl`, and confirmed the
rendered HTML (8 correctly-structured radio cards, "No preference"
checked by default) and that submitting a phase persists and
re-renders as checked on reload.

## Consequences

Two new tests in `test_parent_controls_app.py`: the phase picker
renders with "No preference" checked by default; after saving a
specific phase, reloading the edit page shows that phase's own radio
(and only that one) marked `checked`. All existing `preferred_phase`
tests from decision 0104 (form round-trip, clearing back to no
preference, rejecting an out-of-range phase) needed no changes --
the field's name and values are identical, only the markup around
them changed.

Full suite: 664 passed (4 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).
