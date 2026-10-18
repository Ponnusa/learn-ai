# 0047 — Cap LLM response length instead of chasing hardware bottlenecks

Date: 2026-10-18
Status: Accepted

## Context

After decision 0046's timing logs gave real numbers, and a side
discussion about splitting work across multiple Pis/Picos, product
owner redirected: tune the AI model/call configuration first, since
it's actionable on the current hardware today, before any hardware
change.

Reading the actual backend code turned up a concrete, high-confidence
candidate the earlier analysis hadn't looked at yet:
`OpenAILanguageModelBackend` (`voice/openai_backend.py`) sent no
`max_tokens` at all -- unlike `ClaudeLanguageModelBackend`, which
already had one (`max_tokens: int = 1024`). Every call through it,
including `ConversationService.classify_intent()` (which only ever
needs to answer with one word: STORY/SONG/CHAT/TEACH/NONE), was left
completely unbounded. The Pi's own timing log had already caught this
red-handed: `intent_detection_llm_fallback took 5.19s` for a one-word
answer.

## What shipped

**`OpenAILanguageModelBackend`** gained `max_tokens: int | None = 300`
and `temperature: float | None = None` constructor parameters, sent in
the payload only when not `None`. `300` is a generous cap for this
project's own "short, warm reply" prompt style -- every real reply
observed in testing so far is well under half of it, so this shouldn't
truncate anything that was actually working; it bounds the worst-case
tail instead.

**`ConversationService`** gained an optional `classifier_llm`
parameter, same pattern decision 0018 already established for
`summarizer_llm` (a separate backend instance, defaulting to the main
`llm` if not given). `classify_intent()` now calls
`self._classifier_llm` instead of `self._llm`.

**`setup_demo()`** (`voice_loop_demo.py`) constructs a dedicated
`OpenAILanguageModelBackend(max_tokens=10, temperature=0)` as
`classifier_llm` -- `max_tokens=10` is generous for one word;
`temperature=0` keeps it terse and deterministic rather than
occasionally elaborating, which a higher-temperature, uncapped call
had no reason not to do.

## Consequences

9 new unit tests (303 total passing, 1 skipped where noted in decision
0040): the default `max_tokens` cap is actually sent, a custom
`max_tokens`/`temperature` pair is sent correctly, `max_tokens=None`
omits the key entirely (preserves the old uncapped behavior for any
caller that explicitly wants it), and `classify_intent()` uses the
dedicated `classifier_llm` when given and falls back to the main `llm`
when not.

## Not yet done

This is one concrete lever pulled, not a full resolution of decision
0046's still-open latency question. `reply_generation`/
`tts_synthesize`/`stt_transcribe` were all running 3-10x slower than
this project's earlier Pi benchmark (decision 0012) -- a response-
length cap should help the `reply_generation` side specifically (and
the classify_intent() call very directly), but doesn't address
`tts_synthesize`/`stt_transcribe` latency at all, or confirm/deny how
much of the gap is network conditions versus anything else. Claude's
own `summarizer_llm` already had a 1024-token cap and wasn't touched
here -- lowering it further (session summaries are meant to be "at
most 3 short items") is a smaller, lower-priority follow-up, not done
in this pass. The real next step is still the same as decision 0046
left it: a face-off/face-on comparison (`CHITTI_DISABLE_FACE=1`) and a
fresh session with this cap in place, to see what's actually left.
