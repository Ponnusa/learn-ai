# 0132 — Child profiles page: grid of cards, boxed action buttons instead of one cramped row

Date: 2026-10-28

Status: Accepted

## Context

User feedback: the child profiles page ("child view") lays out as a
single column of full-width rows -- each child's own 6 action links
(Edit, Memories, Engagement, Transcripts, Reading, Progress) plus a
Delete button were all crammed into one `.card-actions` flex row
(`style.css`). For a multi-child household this reads as one long
list of cramped single rows rather than a clean overview. Asked for
a columnar, better-looking layout.

## What shipped

`profiles.html` + `style.css`:

- `.card-list--grid`: the list of child cards is now a CSS grid
  (`repeat(auto-fill, minmax(240px, 1fr))`), so multiple children lay
  out side by side in columns on a wide enough screen instead of one
  long vertical stack, and still collapse to one column on narrow
  viewports -- no JS, no breakpoints to maintain.
- `.profile-actions`: each card's own 6 links are now a 2-column
  grid of boxed buttons (`action-link--boxed` -- bordered, padded,
  centered, light hover fill) instead of plain text crammed into one
  flex line.
- `.profile-delete`: Delete is pulled out of that action grid into
  its own full-width row at the card's bottom, separated by a
  divider -- a destructive action no longer sits visually equal to
  (and squeezed next to) 6 navigational ones.

Scoped to the profiles page only -- `a.action-link` (plain, unboxed)
and the original `.card-actions` flex row are untouched, so every
other page still using them (reading exercises, progress, etc.) is
unaffected.

## Consequences

- No behavior change -- same routes, same links, same CSRF-protected
  delete form; purely a layout/visual change.
- `test_profile_progress_link_appears_on_profiles_page()` and other
  existing tests check for link URLs/text, not the surrounding
  markup, so none needed updating.
