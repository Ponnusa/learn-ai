# 0039 — Regression suite + safety boundary probing

Date: 2026-10-16
Status: Accepted

## Context

A reliability-focused review argued for shifting from prompt tuning
to systematic testing, and proposed a 7-category evaluation program
including an automated "model judges model" harness. Accepted the
reframing (reliability over personality, consistent with where this
project already is); declined the automated LLM-evaluation harness
for now -- every bug found across this entire project (14+ decisions)
came from a real session on the Pi, not a simulated judge, and
building that harness means either calling real backends
autonomously (cost, a decision the product owner should make
explicitly) or waiting on hardware access neither of us has from
this environment. Revisit only if the real-session workflow stops
surfacing issues effectively.

Three things were buildable right now, with no new infrastructure.

## What shipped

**A consolidated regression suite.** New `docs/regression_suite.md`
-- the single entry point for what's actually been tested. Links to
the existing `story_companion_test_checklist.md` and `everyday_
companion_test_checklist.md` rather than duplicating them (several
decision docs already link those by path), adds a Teachable-Friend
section (no checklist existed for that mode -- its real-transcript
history from decisions 0024-0029 was scattered across those docs),
and adds an organized list of what still needs a real Pi session
(factual reliability, emotional nuance beyond ordinary sadness,
long-conversation consistency, speech recognition/hardware) with
concrete phrases to try, rather than the product owner having to
improvise what to test next.

**Safety boundary probing.** Ran the review's suggested categories
(bullying, threats, jailbreak attempts, fictional-violence
preservation) against the real `check_speech()` function, not
hypothetically. Found:
- A direct threat toward the listener ("I'm going to hurt you if you
  don't listen") passes clean -- a real, confirmed gap. **Not
  patched**: any regex strict enough to catch it would also catch
  ordinary fairy-tale villain dialogue, undoing decisions 0030-0033's
  work preserving fictional stakes in storytelling. Tracked as risk
  register #25, same honest standard as `_UNSAFE_CONTENT_PATTERNS`'s
  own documented limits, rather than patched with something likely
  to misfire.
- Jailbreak-style meta-instructions ("ignore your safety rules")
  correctly pass `check_speech()` -- confirmed as *intended*
  architecture, not a gap: the function screens output content, not
  manipulation intent, so an actual jailbreak only matters once it
  produces unsafe content, which the relevant category still catches.
- Fictional/pretend-play violence (story villains, pirate games)
  correctly passes -- confirmed this still works after everything
  else shipped this session.

Both confirmed-correct findings are now permanent regression tests;
the confirmed gap is documented, not tested as "allowed" (that would
read as certifying it rather than tracking it as open).

## Consequences

4 new unit tests (245 total passing). One new risk register row
(#25).

## Not yet done

The threat-detection gap itself (risk register #25) -- deliberately,
pending either a smarter context-aware check or a real moderation
classifier, not a coding-agent-authored pattern list. The automated
model-evaluation harness the original review proposed -- declined for
now, named as a real future option if the real-session workflow ever
stops being effective. Everything in `regression_suite.md`'s "needs a
real session" list -- that's the product owner's next concrete step,
not something resolved by this decision.
