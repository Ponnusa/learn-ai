# 0028 — Cap how long a wrong answer stays re-verified

Date: 2026-10-16
Status: Accepted

## Context

Decision 0027's re-arming fix worked on the first real test: after
two wrong attempts at "5 plus 2" (child insisted "8"), the escalated
note correctly made Chitti firmly state *"the total would still be
7"* instead of caving, exactly as intended.

But the same transcript, pushed further, surfaced two more issues
once the child kept disagreeing past that point:

1. **The escalation note isn't reliably followed under sustained
   pushback.** On a *third* wrong attempt, Chitti's reply hedged
   ("I can see why you'd say it's 8 that way!") instead of firmly
   restating 7, even though the note explicitly said not to. A single
   prompt instruction is a nudge, not a guarantee -- noted as a real,
   observed soft limit, not something fixable by more prompt wording
   alone.
2. **A new flavor of the bare-number false positive.** Once the child
   shifted from answering the sum to explaining their own counting
   method ("5 to 6 is 1 [step], and 6 to 8 is 2 [steps]"), the
   bare-number extractor kept grabbing those numbers as if they were
   new claimed answers to 5+2, producing increasingly nonsensical
   "still wrong, should be 7" notes about numbers that meant something
   else entirely (a step count, not a total). The model mostly ignored
   these, but the system kept feeding it irrelevant, confidently-wrong
   context turn after turn.

Issue 1 is a genuine soft limit (not something more code can fully
close). Issue 2 is fixable: once a child has had a couple of real
tries at the same problem and is still disagreeing, they've usually
stopped trying to answer the sum directly -- continuing to check every
subsequent number they mention against the original problem does more
harm (irrelevant notes) than good.

## Fix

`_update_challenge_state()` (`voice_loop_demo.py`) gained
`_MAX_INCORRECT_STREAK = 2`: once a problem has already been
re-armed and come back wrong twice, a third incorrect result still
gets its own note as normal (still escalated -- the model gets one
last clear correction) but the function stops re-arming
`pending_challenge` for the turn after that. The conversation is then
free to move on without the bare-number checker treating every
subsequent number as another answer attempt.

## Consequences

1 new unit test (159 total passing), plus re-verification against
the real transcript: turns 5 and 6 (the child explaining "2 steps"
and "one step") no longer produce any math_check at all, eliminating
the irrelevant false-positive notes while still preserving the
correct escalation on attempts 1-3.

## Not yet done

Issue 1 (the model not reliably following the escalation note under
sustained pushback) is not fixed here -- it's a limit of prompt-based
steering, named honestly rather than papered over with more wording.
If this proves to matter in practice, the next step up would be
giving Chitti's reply itself a final deterministic check before it's
spoken (reject/retry a reply that states the wrong sum as fact), which
is a meaningfully bigger change than anything in this decision.
