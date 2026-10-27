# 0130 — Disable the thinking fillers: fixed lines are content-blind

Date: 2026-10-27

Status: Accepted

## Context

Real-hardware log:

```
You said: I am sad.
Chitti: Let me see what I can come up with here...
```

`_THINKING_FILLERS` (decision 0050, most recently tuned by decisions
0117/0121/0124) is a fixed pool of 6 lines spoken while an LLM reply
is still generating, picked at random with no awareness of what the
child actually said. Said right after "I am sad," any of them reads
as flippant rather than attentive -- there's no way to pick a "safe"
line from a fixed, content-blind pool, because the pool was never
built with the turn's content in mind at all. The same risk exists
for any other emotionally-loaded turn, not just this one example.

## What shipped

New `_THINKING_FILLERS_ENABLED = False` module constant.
`_speak_while_thinking()` now returns immediately (speaks nothing)
when it's `False`, same as its existing early return when the real
task is already done. The pool, the escalation-stopping logic, and
every `_generate_with_thinking_filler()` call site are all left
exactly as they are -- disabled, not deleted, so the mechanism is
ready to re-enable the moment there's either a genuinely neutral,
content-blind line (e.g. a short thinking sound instead of words) or
real context-aware phrasing, without rebuilding any of this.

Every test that exercises the actual filler-speaking behavior now
sets `_THINKING_FILLERS_ENABLED = True` via `monkeypatch` first (that
behavior itself is unchanged and still correct); a new test confirms
the default (disabled) path speaks nothing at all.

## Consequences

- Chitti now waits in silence (face still shows PROCESSING) while an
  LLM call is in flight -- the latency-masking decision 0050 shipped
  for is gone until this is revisited, traded for not risking a
  tone-deaf line on an emotional turn.
- Two existing tests (`test_carried_over_text_gets_a_real_reply_without_another_capture`,
  `test_fallback_tier_switch_declined_stays_in_current_mode`) hardcoded
  one `_speak()` call for the filler in their scripted `side_effect`
  lists -- updated to drop that slot, since the real reply's own
  `_speak()` call is now the next one in line.

## Not yet done

- Deciding what, if anything, replaces the filler (a non-verbal
  thinking sound, or genuinely context-aware text generated per turn)
  is explicitly out of scope here -- this is a stop-the-bleeding
  disable, not that redesign.
