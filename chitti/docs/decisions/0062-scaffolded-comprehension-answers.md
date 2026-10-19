# 0062 — Scaffolded comprehension answers

Date: 2026-10-19
Status: Accepted

## Context

An external review of a real Pi log flagged what it called the
biggest instructional problem in Reading Partner: when a child's
comprehension answer is wrong, Chitti immediately reveals the correct
detail in the same breath. Real example from the log:

> You said: "It's cheese and apple."
> Chitti: "Oh, that's sweet! The bunny actually sees a red apple in
> the garden and even shares it with a little bird. How kind is that?"

Confirmed as a real gap: `reading/comprehension.py`'s
`build_reaction_prompt()` (decision 0059) explicitly told the model
to "acknowledge what they said and, if it helps, gently adds the real
detail from the story" -- there was no "give one clue, let them try
again" step at all.

**Explicitly rejected from the same review**: replacing the hint-and-
retry ladder (decision 0052) with a general-purpose "reading coach"
LLM that returns a JSON `action` field deciding what to do next. The
hint ladder is already fully deterministic (`reading/hints.py`'s
`pick_hint_word()`/`build_hint_line()`, zero LLM involvement) and
already tested as reliably holding the same target word across all
three stages. Moving that decision into an LLM would trade a reliable,
cheap, fully-tested system for a less predictable one, against this
project's established "deterministic over LLM wherever possible"
discipline (decisions 0051 onward). Not adopted.

## What shipped

**`reading/comprehension.py`**: `build_reaction_prompt()` gained
`attempt_number`/`max_attempts` parameters (default `1`/`2`) and now
branches its instruction -- before the last attempt, explicitly "do
NOT reveal the correct detail yet, give ONE small clue... and invite
them to try again"; on the last attempt, "explain the real detail
yourself... never ask them to try again." The reply format changed
from free text to two labeled lines (`STATUS: resolved|needs_retry` /
`SAY: ...`), same "ask for a strict, simple format, parse
deterministically" convention this project already uses everywhere
else. New `parse_comprehension_reaction()` parses it, defaulting to
`resolved` (and a safe fallback line) on any malformed reply -- a
parse hiccup must never leave the child stuck in a retry loop or get
silence. New `ComprehensionReaction` dataclass (`text`, `needs_retry`)
is the shared return type.

**`conversation/service.py`**: `react_to_comprehension_answer()`
gained the same `attempt_number`/`max_attempts` parameters, now
returns `ComprehensionReaction` instead of the bare `ConversationResult`,
and screens the parsed `text` through the existing `_screen()` exactly
as before -- if that screening blocks the text, `needs_retry` is
forced `False` regardless of what the model asked for, so a safety
block can never turn into a retry loop.

**`voice_loop_demo.py`**'s `_run_comprehension_questions()`: each
question's single capture+react became a bounded loop of up to 2
attempts -- captures an answer, reacts, and only captures a second
answer if `reaction.needs_retry` is `True`. The second call's own
prompt guarantees a resolution regardless of the child's answer, so
this is *never* open-ended: at most one extra capture and one extra
LLM call per question, not a Socratic back-and-forth.

## Consequences

6 new/extended tests in `test_reading_comprehension.py` (the two
prompt branches by attempt number; `parse_comprehension_reaction()`
reading both labels and its malformed-input fallback). 2 new tests in
`test_conversation_service.py` (`needs_retry=True` on a `needs_retry`-
labeled reply; a blocked reply forces `needs_retry=False` even when
the model itself asked for a retry). 2 new end-to-end tests in
`test_voice_loop_demo_intent.py` (a wrong-then-right answer pair gets
exactly one clue before resolving, in order; a resolved first answer
never consumes a second capture at all -- proven by a side-effect
list with no spare entry for one). 2 pre-existing end-to-end tests
updated to the new `STATUS:`/`SAY:` fake-reply format. Full suite: 471
passed, 1 skipped (pygame unavailable in this dev environment,
pre-existing).

## Not yet done

- More than one retry round per question.
- Any change to the hint-and-retry ladder (decision 0052) -- stays
  fully deterministic, no LLM involvement, by deliberate choice.
- Live, speech-synced teleprompter highlighting -- already tracked as
  its own future evaluation in decision 0004's "Open follow-ups."
- A shared cross-phase `attempt`-state-machine data model -- the
  existing per-turn local variables already hold what each phase
  needs; a unified model spanning reading position, hints, and
  comprehension retries is a bigger, separate architectural question.
