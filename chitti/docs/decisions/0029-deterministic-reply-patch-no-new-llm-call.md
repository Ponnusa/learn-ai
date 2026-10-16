# 0029 — Deterministic patch for an unresolved escalated correction

Date: 2026-10-16
Status: Accepted

## Context

Decision 0028's "not yet done" section named the soft limit directly:
on sustained pushback, Chitti doesn't always follow the escalation
note reliably. A real example: *"I can see why you'd say it's 8 that
way!"* -- vague hedging, not a flat agreement, but it never actually
states the correct answer (7) either.

A second review proposed a "narrow deterministic guard" on Chitti's
own reply rather than trusting the prompt note alone -- the right
instinct, matching what decision 0028 already flagged as the next
step. But the proposal's own example of "detecting a conflicting
claim" assumed a clean, checkable restatement. The real failure here
isn't clean: there's no restated equation to catch, just agreement
with no number at all. A guard that only looks for a restated wrong
equation would have missed this exact case.

The user then asked, pointedly: no new LLM call, right? Correct --
the fix below adds zero additional API calls.

## Fix

`education/math_check.py` gained `mentions_number(text, number)`: a
small, honest, purely deterministic check for whether a specific
number appears anywhere in a reply, reusing the existing bare-number
token pattern.

`voice_loop_demo.py`'s new `_patch_if_still_unresolved(result,
math_check, already_tried)` runs only when a math_check is incorrect
*and* already escalated (`already_tried=True` -- the same signal
decision 0027 introduced). It checks two things, both deterministic:

1. Does the reply restate the child's wrong claimed sum as an
   equation (`extract_addition_claim()` match)?
2. Does the reply fail to mention the correct sum anywhere at all
   (`mentions_number()`)?

If either is true, a short, fixed sentence is appended stating the
correct answer -- no retry, no second LLM call, no loop. On a reply
that already does the right thing (states the correct number,
doesn't affirm the wrong one), nothing is touched. On a first,
non-escalated attempt -- where *not* stating the answer yet is the
correct behavior per decision 0025 -- the patch doesn't fire at all.

This is deliberately not a universal sentence validator: it only
activates inside the already-narrow math_check path, only once a
correction has already been tried and failed once, and it checks for
one specific, checkable thing (the right number showing up) rather
than attempting to judge tone, hedging, or reasoning quality in
general.

## Consequences

8 new unit tests (165 total passing), including the real "I can see
why you'd say it's 8 that way!" case, a clean wrong-restatement case,
a reply that already does the right thing (untouched), a first
non-escalated attempt (untouched), and a blocked reply (never
patched).

## Not yet done

The appended sentence is a fixed template, not phrased by the model
-- it will read as a slightly abrupt tonal shift when it fires. That's
an accepted tradeoff for a fallback path that should rarely trigger in
practice (the escalated prompt note already works most of the time
per decision 0027/0028's own testing); not worth generating variety
for a safety-net sentence.
