# 0022 — Fix: story title never passed to the model or the session summary

Date: 2026-10-13
Status: Accepted

## Context

Reported live: Story Companion's Q&A discussion about a story wasn't
showing up in memory the way Teachable-Friend's taught facts do, and
the model has no way to answer something as simple as "what's this
story called?".

## Root cause

`_run_story_companion()` only ever passed `story.content` (the body
text) to `conversation.story_companion_reply()` and into the
in-memory `messages` list used for both the live conversation and the
end-of-session summary. `story.title` was never passed anywhere past
the one-time `_remember_story_read()` call at the start of the
session -- not to the model answering questions, and not to the
summarizer trying to recall what was discussed afterwards. A child
asking "what's this story called?" had no way to get a real answer,
and a session summary had no way to name the story a Q&A exchange was
actually about.

Separately: unlike Teachable-Friend, which writes a durable
`LEARNING_STATE` memory for each fact taught *as it happens*, Story
Companion's Q&A discussion was only ever captured by the one
end-of-session `DAILY_SUMMARY` call -- itself only reliable since
decision 0021's crash fix. This is a known, accepted design gap (not
changed here): decision 0018 deliberately summarizes once at session
end rather than after every turn, to avoid cluttering memory with
trivial exchanges, same as Teachable-Friend's own taught-fact
threshold.

## Fix

- `build_story_companion_prompt()` gained an optional `story_title`
  parameter, included in the system prompt as `read the following
  story called "X"` when given.
- `ConversationService.story_companion_reply()` threads an optional
  `story_title` through to it.
- `_summarize_and_remember_session()` gained an optional `story_title`
  parameter; when given, it's prepended to the transcript sent to the
  summarizer as `(discussing the story: X)`, so the resulting summary
  can actually name the story.
- `_run_story_companion()` now passes `story.title` to both call
  sites.

## Consequences

2 new unit tests (118 total passing): the model's system prompt
includes the title when given, and the summarizer's transcript
includes it too.

## Not yet done

Individual Q&A exchanges during a story discussion are still only
captured via the end-of-session summary, not per-turn like taught
facts are -- intentional per decision 0018's own reasoning, not
revisited here. Separately raised and still open: whether the
summarizer should be fed the child's lines only (to keep memory
focused on what the child said/asked) versus the full transcript
including Chitti's replies (needed since the actual learned content,
e.g. a translation, is usually in Chitti's answer, not the child's
question) -- recommendation is to keep the full transcript for this
reason; not changed in this pass.
