# 0035 — Everyday Companion: bilingual prompt line + test checklist

Date: 2026-10-16
Status: Accepted

## Context

A review of decision 0034's Everyday Companion prompt confirmed two
items were already shipped ("vary your moves," trusted-adult
guidance) and pushed back correctly on a third (a "defined safety
policy" for persistent distress/bullying/danger is explicitly,
deliberately out of scope -- risk register #15, needs qualified
clinical input, not a coding fix; reaffirmed, not revisited here).

Two real, small, approved additions remained:

1. Finnish/bilingual behavior was left fully implicit in the prompt.
2. No repeatable manual test script existed for this mode, unlike
   Story Companion's (`story_companion_test_checklist.md`).

A third item -- mode-switching mid-conversation (the review's
"conversation router") -- is real and confirmed (today, mode choice
happens once at the menu; none of the three loops can hand off to
another mode), but it's genuine control-flow work, not a prompt
tweak. Explicitly deferred to its own follow-up plan, per the product
owner ("we can plan mode-switch later, but remember that") --
recorded in memory, not just here, so it survives past this session.

## Fix

- `build_everyday_companion_prompt()` gained one instruction: follow
  whichever language the child uses (Finnish, English, or a mix),
  switch when asked, don't correct language choice unless they asked
  to practice or translate. **Honestly scoped**: Whisper STT is still
  hardcoded to English (decision 0020), so this doesn't make spoken
  Finnish actually work -- a child speaking Finnish still gets
  mis-transcribed before this prompt ever sees it. The line is cheap
  and correct as a standing instruction, not a claim that Finnish is
  solved.
- New `docs/everyday_companion_test_checklist.md`, mirroring the
  Story Companion checklist's format -- 10 scenarios from the
  review's own acceptance-test table, each marked with automated
  coverage or "not yet working" where that's the honest answer (rows
  7 and 9, blocked on the STT fix and mode-switching respectively).

## Consequences

1 new unit test (214 total passing) confirming the bilingual
instruction is present.

## Not yet done

Mode-switching (tracked in memory:
`project_chitti_mode_switching_deferred.md`) and the full Finnish/
bilingual pipeline fix (STT language plumbing, a `ChildProfile`
language field, real audio testing) remain open, named explicitly so
neither gets silently forgotten.
