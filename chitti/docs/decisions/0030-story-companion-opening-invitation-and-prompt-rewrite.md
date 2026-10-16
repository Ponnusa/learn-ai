# 0030 — Story Companion: opening invitation + companion-not-quiz prompt rewrite

Date: 2026-10-16
Status: Accepted

## Context

A detailed design review argued Story Companion should be a real
companion experience, not a robot that reads a story and then runs a
comprehension quiz. Checked against the actual code before acting on
any of it:

- `_run_story_companion()` read the story aloud, then went straight
  into `_capture_and_transcribe()` and waited silently -- Chitti never
  spoke first. The review's single biggest, most concrete gap, and a
  real one.
- `build_story_companion_prompt()` was pure comprehension-Q&A:
  *"Answer the child's questions about it using ONLY what's in the
  story... never say anything that contradicts the story."* Accurate
  and appropriately cautious about story *facts* (decision 0016's
  fix), but nothing invited the child's own perspective, allowed
  imaginative "what if" extension, or said it was fine to just stop.
- `StoryRecord` has only `id`/`title`/`content`/`created_at` -- no
  age range, themes, or conversation metadata. The review's
  "structured story metadata" proposal is real schema + Parent
  Controls UI work, not something to fold into this pass.

Teachable-Friend's math-check path is explicitly frozen for this
pass, per the product owner's direction -- nothing here touches it.

## What shipped

**Chitti speaks first.** New `ConversationService.story_opening_
invitation()`, same one-shot pattern as the existing `welcome_back_
greeting()` (a synthetic trigger message, since `generate_reply()`
needs at least one). `_run_story_companion()` calls it right after
the story is read and remembered, before the child says anything, and
appends the result to `messages` like any other turn.

**Companion framing, not just grounding.** `conversation/prompts.py`
now has a shared `_story_companion_core()` used by both the opening
line and the ongoing conversation: keeps decision 0016's "never
contradict story facts, say 'not sure' rather than guess" rule
unchanged, but adds an explicit imagination carve-out (invented
endings/adventures are fine, just be clear it's invented, not
recited), "one question is enough, don't stack them," "letting the
child stop or change the subject is a complete, successful
interaction," and "don't assume the child's own feelings from a
character's, and point toward a trusted adult for anything personal
or distressing" -- same spirit as the safety-escalation stance
already established elsewhere in this project, not a new policy.

**Age-aware tone, no new field.** `ChildProfile.age` already existed
and was simply never threaded into Story Companion. `main()` already
holds the full `profile` object -- `_run_story_companion()`,
`story_companion_reply()`, and `story_opening_invitation()` all gained
an optional `child_age` parameter, sourced from `profile.age` at the
one call site. Framed in the prompt as a starting point, not a rule.

## Consequences

21 new/updated unit tests (177 total passing): the opening invitation
(story + title in the prompt, asks for exactly one line, screened
like any other speech), the shared core's imagination/stop-gracefully
wording, age tuning present/absent correctly, and the existing title
regression (decision 0022) still passing unchanged.

## Not yet done

Explicitly deferred, not forgotten: a structured per-story metadata
schema (age range, themes, language, parent-configured conversation
permissions) -- real schema and Parent Controls UI work. No app-level
"pick one of five conversational styles" selection logic either -- the
rewritten prompt gives the model a real repertoire to draw from
naturally; building a mode-selector would be premature engineering
without evidence the prompt alone can't do it. Storytelling also stays
outside decision 0023/0024's engagement/correctness tracking, by
design -- it isn't being instrumented as a learning activity.
