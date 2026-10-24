# 0107 — A per-story detail page and a per-child mastery roadmap, modeled on Open Phonics' own UI

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback, pointing at two real pages on the Open Phonics
source app itself:

> "go here and see http://localhost:8080/stories/sam-sat/ this is
> how it should show even on our app so it looks nice... parent
> knows what word the child is learning for each story similar
> ui, also check this atleast we can show like this roadampa for
> each story what the child has mastered.. http://localhost:8080/roadmap/.
> all of this but with minimal things and green or red or yellow or
> some indication so parent knows how the chld is performing.."

Both URLs are on the user's own local dev server, unreachable from
here -- read the real source instead, from the already-cloned
reference repo: `open-phonics-reference/src/_includes/layouts/story.njk`
(the per-story page) and `open-phonics-reference/src/pages/roadmap.njk`
(the lesson roadmap).

Two fields the source project's own `.md` frontmatter always had,
but decision 0104's conversion hadn't vendored yet: `description`
(a one-line summary) and `words` (each target word tagged with the
lesson that introduces it -- the thing a parent most wanted: "parent
knows what word the child is learning for each story"). Re-ran the
same conversion approach against the same 30 source files to pull
both in.

Kept deliberately minimal, per the request: the roadmap is **per
story**, not per Open Phonics' own 150-lesson sequence (Chitti has no
equivalent lesson track of its own), and **per child**, not global --
mastery is inherently per-profile. Three colors only
(green/yellow/red), reusing decision 0103's own
`_weakest_mastery_for_miscues()` convention rather than inventing new
scoring: an untracked grapheme counts as `0.0`, same as a
tracked-but-weak one, so a story never attempted shows the same red
as a weak one. No separate "never attempted" state for this first
version.

## What shipped

**`reading/story_library.py`**: `LibraryStory` gains `description:
str` and `words: list[tuple[str, int]]`, plus a `.text` property
(`" ".join(self.pages)`, mirroring `GeneratedBook.text`). All 30
vendored entries carry both fields now. New `get_story(slug) ->
LibraryStory | None` (linear scan, no index needed at 30 entries).
New `mastery_color_for_story(story, profile) -> "green" | "yellow" |
"red"`: walks every word in the story's own text, decomposes it via
`decodability.decompose()`, takes the minimum tracked `p_mastery`
across every grapheme found (untracked counts as `0.0`) -- green at
`>= curriculum.MASTERY_THRESHOLD` (0.95), red below 0.5, yellow
between.

**`parent_controls/app.py`**:
- New `GET /reading/<slug>` (`reading_library_story_view`): the
  story's own page -- title, phase, description, full text,
  "Words in this story" (each tagged with a lesson-number badge),
  comprehension Q&A shown with question *and* answer together
  (parent-facing, no reveal toggle). 404s for an unknown slug.
- `create_app()` now also instantiates `ReadingRepository` (wasn't
  wired into this app at all before -- only the unrelated
  `ReadingExerciseRepository` was).
- New `GET /profiles/<profile_id>/progress`
  (`profile_progress_view`): loads that child's own `ReadingProfile`
  and, for every phase, every one of its stories, shows a
  green/yellow/red dot from `mastery_color_for_story`, each linking
  to that story's own detail page.

**Templates**: new `reading_library_story.html` and
`profile_progress.html`. `reading_library.html`'s story titles are
now links to their own detail page. `profiles.html` gains a
"Progress" action link alongside the existing "Edit / Memories /
Engagement / Transcripts / Reading" row (kept separate from the
existing "Reading" link, which is decision 0052's unrelated
upload-an-exercise page). `style.css` gains the three mastery-dot
colors and the word-badge styling, no new palette system.

Verified against a real server round trip (a throwaway temp SQLite
DB, not the real `chitti/data/chitti.db`, to avoid touching real
parent data or needing the real PIN): PIN setup, login, create a
profile, then fetched `/reading/sam-sat` and
`/profiles/<id>/progress` as real authenticated requests and
inspected the rendered HTML -- both render exactly as designed,
including every word's lesson badge and a fresh profile correctly
showing red across the board.

## Consequences

Seven new tests in `test_story_library.py` (all vendored stories
have a description and words; `.text` joins pages correctly;
`get_story` finds a known slug and returns `None` for an unknown
one; `mastery_color_for_story` returns green/red/yellow for a
fully-mastered, fresh, and mixed profile respectively). Six new
tests in `test_parent_controls_app.py` (story detail page shows
description/word-lesson-badges/Q&A and 404s for a bad slug; the
library page links to each story; the Progress link appears on
`/profiles`; the progress page lists every phase and shows red for a
fresh profile, green once a story's graphemes are all mastered).

Full suite: 681 passed (3 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

Still only three buckets, no distinct "never attempted" state --
if a parent finds "red" confusing for a story their child simply
hasn't gotten to yet, that's a natural, separable follow-up. The
roadmap is scoped to Chitti's own story library only, not any
broader lesson-by-lesson view; that would require a lesson sequence
of Chitti's own, which doesn't exist.
