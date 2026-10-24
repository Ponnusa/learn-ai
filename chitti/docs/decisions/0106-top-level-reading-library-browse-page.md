# 0106 — A top-level "Reading" page browsing the story library by phase

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback: decision 0104's story library had no way to browse
it at all -- a parent could only pick a phase blind, from inside one
child's Edit Profile page, with no visibility into what's actually
in that phase ("is it possible for me to see the story provisioned,
as a parent i can see for each level what stories are there etc,
just like our openphonics app"). Reading also had no presence in the
top-level nav at all -- everything reading-related lived under a
specific child's profile.

## What shipped

**`reading/story_library.py`**: new `stories_by_phase() -> dict[int,
list[LibraryStory]]` -- every vendored story grouped by phase, each
group sorted by its own `order`. A plain read-only accessor, kept
separate from `pick_library_book()` (the one function that actually
selects/consumes a story for a session) -- browsing the library and
assigning a child to read from it are different concerns.

**`parent_controls/app.py`**: new top-level `GET /reading` route
(`reading_library_view()`), alongside `/profiles` and `/stories`,
not nested under a profile id. Deliberately read-only -- which phase
a specific child starts at is still set from their own Edit Profile
page; this page only answers "what's in the library."

**`parent_controls/templates/reading_library.html`** (new) and
**`base.html`**: a "Reading" nav link between "Profiles" and
"Stories"; the page itself lists every phase (title + subtitle) with
its own stories as cards (title, sentence count, comprehension
question count), same `card-list` visual language as every other
listing page in this app.

Verified against the real running app, not just the unit tests:
logged into the already-running dev server (PIN already set from
decision 0105's own verification) and confirmed all 7 phases and
their stories render correctly end to end, nav link included.

## Consequences

Two new tests in `test_parent_controls_app.py` (`/reading` lists
every phase and a story from each end of the range; the nav link
appears on another page). One new test in `test_story_library.py`
for `stories_by_phase()` itself (groups and orders correctly, every
story accounted for).

Full suite: 667 passed (4 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

Reading exercises (`/profiles/<id>/reading-exercises`) and the
per-child reading settings (pace, font, preferred phase) stay exactly
where they are, in Edit Profile -- they're inherently per-child, not
global library content, so they don't belong on this page. This page
is intentionally just the catalog.
