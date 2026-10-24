# 0104 — Vendor the Open Phonics story library, phase-selectable by parents

Date: 2026-10-24
Status: Accepted

## Context

Most parents never use the "upload your own reading exercise" path
(`parent_controls`'s reading-exercises feature) -- writing a story by
hand is real effort. Direct request: let a parent instead just pick
a phase, and Chitti serves an already-written, already-leveled story
for it -- no typing, no LLM call needed for that session. Performance
against that specific story should be recorded the same way it
already is for any other book. LLM-generated stories become a
later/secondary tier, not the default, once this exists.

Source confirmed directly, not assumed: `C:\repos\open-phonics-reference`
is a local clone of **Open Phonics**
(github.com/jonajinga/open-phonics, MIT licensed, by Pikes Peak Web
Designs, "Based on the Direct Instruction methodology developed by
Siegfried Engelmann"). 30 markdown stories in `src/stories/*.md`,
each with YAML frontmatter -- `title`, `phase` (1-7), `order`, a
`words` list (word -> the lesson that introduces it), and a
`comprehension` list of `{q, a}` pairs -- followed by the story body.
The user has stated they hold the rights to copy this content
independent of its own MIT license -- both documented in the new
module, same precedent decision 0091 already set for the phonics
sound clips (state the source, state the license, state the user's
own rights representation, then proceed).

**Key simplifying fact, verified against the code, not assumed**:
mastery attribution (`assess()` -> `attribute_evidence()` ->
`update_from_evidence()`) already works against *any* text, by
decomposing it with Chitti's own `decodability.decompose()` --
independent of which taxonomy classified the source content. "Phase"
only needed to be a **content-selection key** for the parent; it
never needed mapping onto Chitti's own `curriculum.py`
`LEVEL_SEQUENCE`/`GRAPHEME_LEVEL` for the reading-partner mechanics
(hint ladder, mastery, highlighting, tiered correction) to work
unchanged on a library story.

## What shipped

**`reading/story_library.py`** (new): `LibraryStory` dataclass and a
hardcoded `_LIBRARY_STORIES` literal -- all 30 stories, converted
once (frontmatter parsed, markdown bold markers stripped, paragraph
breaks become pages) via a one-off script, not a runtime markdown/
YAML dependency. Spot-checked several converted stories against
their source `.md` files byte-for-byte for the prose; all 30 parsed
cleanly with the expected phase distribution (3/4/5/3/2/8/5 across
phases 1-7). `PHASES`: brief parent-facing phase metadata (title/
subtitle), taken from the source project's own `phases.js`.

`pick_library_book(phase, objective, completed_slugs) ->
GeneratedBook | None`: same shape as `story_bank.py`'s existing
`pick_story_bank_book()` -- returns the lowest-`order` story at
`phase` not already in `completed_slugs`, or `None` if the phase is
exhausted. Deliberately **not** re-verified against
`decodability.is_word_decodable()` the way the hand-written bank is
-- this content is already vetted by its own authors at its own
phase, and a parent who explicitly picked that phase made a
deliberate choice this shouldn't second-guess.

**`reading/schema.py`**: `GeneratedBook` gains `library_slug: str |
None = None` and `comprehension: list[tuple[str, str]] =
field(default_factory=list)` (both empty for every existing LLM/bank/
exercise book -- no behavior change for them). `ReadingProfile`
gains `completed_library_stories: list[str] = field(default_factory=list)`.
`reading/repository.py` persists it exactly like `sight_words`
already is (separator-joined string column).

**`parent_controls/profiles.py`**: `ChildProfile.preferred_phase:
int | None = None`. `ChildProfileRepository.update()` needed a
dedicated `_UNSET` sentinel for this one parameter specifically --
unlike every other field here, this one's own "no preference" value
(`None`) collides with `update()`'s existing "don't change this
field" convention (also `None`), so a distinct sentinel default was
needed to still let a parent explicitly clear the preference back to
"no preference" through the same method.

**`storage/migrations.py`**: two new `_ensure_column` calls
(`child_profiles.preferred_phase`, `reading_profiles.completed_library_stories`),
following the file's own established pattern exactly.

**`voice_loop_demo.py`** (v1 only -- `_run_reading_partner_v2`
accepts but ignores the new parameter, purely so the one shared
dispatch call site doesn't need to branch its kwargs by which
version is active, same reasoning `initial_text` already uses
there): a new tier, tried **before** any LLM generation, right where
a fresh book is selected -- if `preferred_phase is not None`,
`pick_library_book()` is tried first; only if it returns `None`
(phase exhausted, or no preference set) does the existing LLM ->
hand-written-bank -> word-drill chain run, unchanged. Once a library
book finishes (same point `sessions_completed += 1` / `save()`
already fires), its slug is appended to
`completed_library_stories` -- "record the performance against that
story" is already true for free the moment it flows through the
unchanged assess/mastery pipeline; this one line is just "don't
re-serve the same story." `_run_comprehension_questions()` uses a
library book's own pre-written Q&A directly when present, skipping
`generate_comprehension_questions()` entirely -- reacting to the
child's answer is unchanged, still grounded live in `book.text`, not
the pre-written answer, so a child's own wording is still judged
warmly rather than diffed against one fixed expected string.

**Parent Controls**: `edit_profile.html` gains a "Starting phase"
dropdown (the 7 phases plus "No preference -- Chitti generates
stories"); `app.py`'s `edit_profile` route parses it (empty -> `None`,
otherwise validated against `PHASES`' own ids) and passes it through
to `profiles.update()`.

## Consequences

New `test_story_library.py` (7 tests: full vendored-content sanity
check, phase coverage, lowest-order-unread selection, skips completed
stories, `None` once a phase is exhausted, unknown phase degrades to
`None`, objective passed through unchanged). Extended
`test_voice_loop_demo_intent.py` (a preferred-phase profile gets a
library book with zero `generate_decodable_book`/
`generate_comprehension_questions` calls; the slug is recorded after
it finishes; a second call gets the next story, not a repeat).
Extended `test_parent_controls_app.py` (phase round-trips through
the form; empty selection clears it back to `None`; an out-of-range
phase is rejected). Extended `test_migrations_ensure_column.py` for
both new columns.

Full suite: 662 passed (4 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

No mapping between Open Phonics' phases and Chitti's own
`curriculum.py` levels -- deliberately unnecessary, per the
"key simplifying fact" above; mastery tracking already works on any
text regardless. No cross-session prioritization between a
preferred-phase library story and the existing hand-written
`_STORY_BANK`/LLM paths beyond "try the library first" -- if a parent
sets a phase, every fresh book uses the library until that phase runs
out, with no blending. No UI surfacing of "how many stories are left
in this phase" to the parent -- a reasonable follow-up once this is
used live.
