# 0033 — Story Companion: retell vs. continue, and no forced morals

Date: 2026-10-16
Status: Accepted

## Context

A detailed review proposed a storytelling controller, structured
per-story state, and an output-checker. Before planning any of that,
its 5 "high priority" items were checked against what's already
shipped (decisions 0030-0032):

| Priority | Status |
|---|---|
| Replace "question at the end" habit | Done (decision 0032) |
| Let Chitti contribute to play | Done (decision 0032) |
| Proportionate safety responses | Done (decision 0031) |
| Remove forced morals | Partially done -- real gap confirmed below |
| Distinguish retelling from continuing | Not addressed at all |

Two confirmed gaps, found by re-reading actual transcripts, not
guessing:

- **Retell vs. continue**: "what happens next in the story?" got
  answered with a recap of the already-established ending, not a new
  continuation.
- **Forced morals**: the child explicitly said *"don't teach me a
  lesson, just make it funny,"* and the generated story still ended
  with *"realizing that even a silly mix-up could create a fun
  day"* -- a soft takeaway, despite the explicit request not to have
  one. `_story_companion_core()` had no instruction addressing this.

Both are cheap, prompt-only fixes -- and the review's own recommended
order (start with the prompt, test, only add a controller/state/
checker if gaps remain) matches exactly what this project has been
doing since decision 0030.

## Fix

Two additions to `_story_companion_core()` (`conversation/
prompts.py`), next to the existing imagination carve-out:

1. "Next"/"continue" means inventing new events beyond where the
   story ended, not summarizing it; "again"/"retell" means repeating
   the original faithfully.
2. If the child asks for something funny or explicitly says not to
   teach a lesson, don't end with a "realized that..." / "learned
   that..." takeaway anyway -- end on the joke, the punchline, or a
   warm close.

New `docs/story_companion_test_checklist.md`: the review's 10
scenarios as a repeatable manual-test script for the Pi, each marked
with whether it's backed by an automated prompt-content test or only
checkable by reading a live reply.

## Explicitly deferred

- **Storytelling controller** (intent classification before
  generation, 8 response modes) -- real new architecture. Premature
  before testing whether this prompt-only pass closes the gap, per
  the review's own recommended ordering.
- **Structured per-story state** (`characters`/`setting`/`events`/
  `ending_state`, plus a short-lived scene state for continuations) --
  real schema work beyond today's `StoryRecord` (`id`/`title`/
  `content`/`created_at`). Worth it if the retell/continue fix proves
  insufficient under more testing, not assumed necessary yet.
- **Output-checker/regenerate mechanism** for storytelling
  violations -- the same shape as decision 0029's math-check patch,
  but "did this contain a forced moral" has no cheap deterministic
  check analogous to `mentions_number()`. Revisit only if the prompt
  fix doesn't hold up.

## Consequences

4 new unit tests (200 total passing) confirming the new wording
appears in both the ongoing-conversation prompt and the opening
invitation. The checklist doc is process, not code -- no test for it
beyond existing.

## Not yet done

Same honesty-about-limits as every other prompt fix here: scenarios
6, 7, and 10 in the new checklist have no automated coverage at all,
since judging them requires reading an actual generated reply, not
just checking the prompt contains the right words.
