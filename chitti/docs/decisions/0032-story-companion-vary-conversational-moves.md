# 0032 — Story Companion: vary conversational moves, don't always ask

Date: 2026-10-16
Status: Accepted

## Context

Reviewing the same real transcript that led to decision 0031, a
second pattern stood out: every single Chitti turn ended in a
question -- *"What funny sound would you make?"*, *"What other funny
sounds do you like?"*, *"What kind of adventures do you think a
pooping robot would go on?"*, *"What do you think the aliens would do
next?"*, *"What part of that made you smile the most?"*, *"Would you
join Barnaby's colorful adventure?"* -- with zero exceptions across
the whole conversation.

Decision 0030's prompt already says "one question is enough, don't
stack several in a row" -- but that only guards against multiple
questions *in the same turn*. It says nothing about ending *every*
turn with one, which is its own version of interviewing rather than
playing: the child is always the one expected to contribute the next
idea, and Chitti never does.

## Fix

Added to the shared `_story_companion_core()` (used by both the
opening invitation and the ongoing conversation): don't end every
turn with a question. Vary the move instead -- sometimes ask, sometimes
contribute a small idea of its own to keep the play going (with a
concrete example, same style as other prompts in this project that
show rather than just instruct), sometimes just react with surprise
or amusement, sometimes let a moment be enough without redirecting
it. Also added, prompted by the same transcript's toilet-humor
thread: keep any bodily-function humor light and silly rather than
graphic, especially for younger children.

## Consequences

2 new unit tests (197 total passing) confirming the new guidance
appears in both the ongoing-conversation prompt and the opening
invitation (they share the core, so both should carry it).

## Not yet done

Same honesty-about-limits as every other prompt-wording fix in this
project: this is a nudge toward variety, not a mechanism that
guarantees it. Whether Chitti actually diversifies its conversational
moves in practice is something to verify against the next real
transcript, not assumed from the wording alone.
