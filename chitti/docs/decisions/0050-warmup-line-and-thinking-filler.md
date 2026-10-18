# 0050 — Lullaby warm-up line and escalating "thinking" filler

Date: 2026-10-18
Status: Accepted

## Context

Two product requests, both about how the wait *feels* rather than how
long it actually is:

1. Switching into Lullaby time went straight from silence to the song
   with no transition -- flagged as abrupt; wanted a short warm-up
   line first ("I'm going to play a song for you!"), explicitly fixed/
   pre-decided wording, no LLM call needed just to announce what's
   about to happen.
2. While Chitti is waiting on a real AI reply (PROCESSING state), there
   was only a visual "thinking" face (decision 0044) and otherwise
   silence -- even after decision 0049's persistent-session fix,
   `reply_generation` still legitimately takes several seconds for a
   real conversational reply. Wanted a spoken filler ("let me think...")
   to make the wait feel alive, escalating for longer waits rather than
   one static line, confirmed via AskUserQuestion.

## What shipped

**Lullaby warm-up**: `_run_lullaby_time()` now speaks `f"I'm going to
play {lullaby.title} for you!"` right before calling
`_play_lullaby_file()`. Fixed template, not AI-generated.

**Escalating thinking filler**: `_THINKING_FILLERS`, a fixed list of
three deterministic lines ("Hmm, let me think about that...", "Okay,
just a little longer...", "Almost got it..."). `_speak_while_thinking(task,
...)` speaks them in order, checking before each one whether `task` (the
real AI call) is already done -- stops as soon as it is, never repeats
a line, and simply goes quiet rather than looping once the list is
exhausted. `_generate_with_thinking_filler(coro, ...)` is the actual
integration point: starts `coro` (the real `ConversationService` call)
as a background `asyncio.Task` via `asyncio.ensure_future()`, runs the
filler loop *concurrently* with it, then awaits the task's real result
-- the filler speech and the real AI call genuinely overlap, so this
camouflages latency rather than adding to it. Wired into all four
reply-generating call sites (`teachable_friend_reply`,
`everyday_companion_reply`, `story_companion_reply`,
`story_opening_invitation`), replacing the plain `_timed("reply_generation")`
wrapper each one had -- timing itself is preserved exactly (still
logged from task creation to real completion, regardless of how the
wait was filled), just no longer tied to a synchronous `async with`
block.

## Consequences

9 new unit tests (312 total passing, 1 skipped where noted in decision
0040): `_speak_while_thinking`'s escalation-stopping logic (via a
`_FakeTask` with a controllable `done()` sequence -- real asyncio.Task
scheduling turned out to be unreliable to pin down precisely in tests,
since nothing in a chain of trivial fake coroutines genuinely yields
to the event loop the way real network I/O does) and its "speaks every
filler once, never repeats" behavior (via a Future that's deliberately
never resolved), `_generate_with_thinking_filler`'s pass-through of the
real result, and updates to existing end-to-end tests whose `_speak`
call-count assertions needed the extra filler call(s) accounted for.

Found during testing, worth noting as real production behavior, not
just a test artifact: because nothing synchronous yields control to
the event loop, the background task can't possibly be "done" on the
very first check -- so at least one filler always plays, even for a
reply that would otherwise return near-instantly. In practice this is
harmless (real network calls are never that fast) and arguably
desirable (a brief "let me think" before answering reads as natural,
not just latency-masking).

## Not yet done

Filler wording is fixed and shared across all three conversation
modes -- no per-mode flavor (e.g. a story-specific or teaching-
specific filler) was built, matching the "pre-decided wording" framing
of the request. The lullaby warm-up line and the thinking filler are
unrelated mechanisms shipped together only because both were raised in
the same conversation.
