# 0048 — No confirmation when switching into Just Chat

Date: 2026-10-18
Status: Accepted

## Context

Real Pi transcript, found live: child was in Teachable-Friend mode,
said "I am really sad," got an empathetic reply, then said "My friend
is not talking to me. I tried everything but he is still not talking
to me." That sentence contains "talking," hit decision 0046's LLM-
fallback tier, was classified CHAT, and Chitti asked: "Sounds like you
want to just chat -- is that right?"

Flagged directly: that question is wrong in this moment. The child had
already said something emotional; a confirmation question right then
reads as Chitti not actually listening, not as a careful safety check.
Decision 0046's reasoning for confirming fallback-tier detections
still holds for Story/Song/Teach -- landing in the wrong *activity* is
genuinely disruptive -- but it doesn't hold for Just Chat: there's no
wrong activity to land in by mistake, since Just Chat is the neutral,
supportive default mode. Confirming here has a real cost (delaying and
undercutting exactly the empathetic reply the moment calls for) and no
corresponding benefit.

## What shipped

`_detect_switch_intent()`: after resolving `mode_code` (and the
current-mode-suppression check from decision 0042's addendum), a new
one-line override -- `if mode_code == "3": confident = True` -- makes
switching into Just Chat always confident, regardless of which tier
produced the match. Everything else about the function (the three
detection tiers, the current-mode no-op check, the `(mode_code,
confident)` return shape) is unchanged, and `_confirm_switch()` itself
didn't need to change at all: it's simply never called for this case,
since `confident or await _confirm_switch(...)` short-circuits.

## Consequences

2 new unit tests (305 total passing, 1 skipped where noted in decision
0040): `_detect_switch_intent()` returns `confident=True` for a
Just-Chat match that came through the LLM-fallback tier specifically
(the actual case that was wrong), and an end-to-end test driving
`_run_teachable_friend` through the real emotional-statement scenario,
asserting the switch happens with **zero** TTS calls before it -- no
confirmation question is ever spoken, and the triggering text carries
straight through to get a real reply in Just Chat next.

## Not yet done

Story/Song/Teach keep asking for confirmation on the fallback tier,
unchanged -- this decision is deliberately narrow to the one mode
where confirming has no upside. Whether an emotionally-loaded
utterance should *also* skip the fallback tier's LLM call entirely
(going straight to Just Chat without even classify_intent()'s
latency) wasn't considered here; this pass only removes the spoken
confirmation step; it's a smaller, separate question.
