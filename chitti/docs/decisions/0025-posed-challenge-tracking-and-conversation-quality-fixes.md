# 0025 — Posed-challenge tracking + three conversation-quality fixes

Date: 2026-10-15
Status: Accepted

## Context

A real Teachable-Friend transcript, independently reviewed twice,
confirmed exactly the gap decision 0024 flagged as deferred: when
*Chitti* poses an addition challenge ("if you have 2 chocolates and
get 3 more...") and the child replies with a bare number ("4."), the
deterministic checker never fired -- the model judged the arithmetic
itself, unverified. In the transcript it happened twice and the model
got both right (2+3=5), but that's luck, not a guarantee, and it's
the *more common* real pattern -- a curious-peer robot naturally ends
up posing the next challenge rather than waiting for the child to
restate a full equation.

The second review also surfaced three smaller, independently-cheap
fixes, confirmed against the actual transcript text, not hypothetical:
1. A wrong answer got corrected by immediately stating the right
   number, without first asking how the child got theirs.
2. Chitti asked a question inside an improvised story and then
   answered it itself before the child replied ("...how many tasty
   treats did they have? That's right! They had 2 treats!").
3. Chitti defaulted to tutor-style Q&A throughout and never once
   invited the child to teach *it* a method -- the whole premise of
   Teachable-Friend.

**Rejected from the same review**: formal "Learning mode / Free-
conversation mode / Story mode" as a state machine, and any
persistent proficiency/mastery tracking. Both are real, bigger scope
decisions (the same "Milestone-2/3 ambition" flagged in earlier
design discussions) -- not built here. Decisions 0023/0024 already
deliberately track nothing about correctness over time; that stance
is unchanged.

## 1. Posed-challenge tracking

`education/math_check.py` gained `extract_posed_challenge()` (finds
two number tokens near "plus"/"+"/"more" in *Chitti's own* reply) and
`extract_bare_number()` (the *last* standalone number in a reply --
not the first, since counting aloud like "1, 2, 3, 4, 5." should
resolve to the final tally).

**Design choice**: retroactively recognize a posed challenge from
Chitti's own free-form text, rather than having the app pre-choose
operands and command the model to use them. App-mandated injection
would make every math-adjacent turn feel more scripted (conflicts
with "never feel tested"); retroactive extraction degrades safely --
a missed extraction just falls back to today's unverified behavior,
no regression, and matches this codebase's existing style of small
deterministic regex helpers rather than a new control-flow mechanism.

`voice_loop_demo.py`'s `_run_teachable_friend()` tracks
`pending_challenge: tuple[int, int] | None` across turns (in-memory,
per-session, no persistence). The resolution logic was extracted into
`_resolve_math_check()`: a self-stated equation always wins; otherwise
a bare number is checked against the pending challenge. Cleared every
turn whether resolved or not, so it never attaches to an unrelated
later exchange (e.g. the real transcript's later, unrelated milk-
chocolate tangent).

Restricting the regex to actual number tokens (not any `\w+`) matters
here specifically: an earlier draft let "chocolates" match as a second
operand purely because it was the next word after a number, near
"more". Verified against the real correction text, which mentions two
different numbers (the recap "2 chocolates and 3 more" and the stray
"5 chocolates" from the correction itself) -- the fix correctly
resolves to the real operands (2, 3), not the unrelated 5.

## 2-4. Conversation-quality wording fixes

- `build_math_check_note()`'s incorrect branch now asks the child to
  walk through how they got their number (or offers one small hint)
  *before* giving the full countable walkthrough -- only escalating to
  that if they're still stuck or ask directly.
- `TEACHABLE_FRIEND_SYSTEM_PROMPT` gained one instruction not to ask a
  question (including inside a story) and then answer it in the same
  turn.
- Same prompt gained one instruction to invite the child to teach
  *their own* method when it feels natural, reinforcing the existing
  "curious peer" framing rather than defaulting to tutor-style Q&A.

All three are prompt wording only -- best-effort, not mechanically
enforceable, same honesty-about-limits as everything else in this
project.

## Consequences

14 new/updated unit tests (150 total passing): `extract_posed_
challenge()`/`extract_bare_number()` behavior including the real
false-positive case found above, `_resolve_math_check()`'s priority
and clearing rules, and the updated prompt-note wording assertion.

## Not yet done

Rejected, not deferred: conversation modes and proficiency tracking
(see Context). The posed-challenge extraction remains heuristic on
free-form narrative -- a false miss just means no check (safe); a
false match produces one odd follow-up note (low-stakes, not a safety
issue), not something stronger guarantees exist against yet.
