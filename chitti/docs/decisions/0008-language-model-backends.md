# 0008 — OpenAI and Claude LanguageModelBackend implementations + Finnish benchmark script

Date: 2026-10-13
Status: Accepted; benchmark script built, live run pending `.env` setup

## Context

Third real feature after the Safety layer (0006) and Memory Service
(0007). Decision 0004 said the final `LanguageModelBackend` choice needs
a real Finnish-quality comparison before committing — this builds both
candidates plus the script to actually run that comparison, rather than
deciding on guesswork.

## What was built

- `voice/openai_backend.py`: `OpenAILanguageModelBackend` — same
  lightweight `requests`-based HTTP pattern as
  `pixel-ai/pixel_direct_llm.py`, not the official SDK. Blocking
  `requests.post` offloaded via `asyncio.to_thread` so it doesn't stall
  the event loop, matching `LanguageModelBackend`'s async contract
  honestly rather than faking it.
- `voice/claude_backend.py`: `ClaudeLanguageModelBackend` — same pattern
  as `pixel-ai/pixel_direct_claude.py`, Anthropic's Messages API shape
  (`system` as a top-level field, `x-api-key` header).
- `config/loader.py`: added `load_dotenv()` at import time — the exact
  fix for a real bug hit earlier in `pixel-ai` (`pixel_direct_llm.py`
  read `os.environ` directly with no `.env` loading of its own before
  anything else had loaded it). Loading it at the one module every
  env-reading path already goes through avoids repeating that mistake
  here.
- `scripts/benchmark_finnish.py`: runs four Finnish prompts (greeting,
  story request, simple maths, a Teachable-Friend-style "I taught you
  something" turn) against both backends, printing replies with
  per-call latency. Deliberately does **not** auto-score Finnish
  fluency — that needs a Finnish speaker's judgment, not a guess from
  this agent.
- 6 new unit tests (47 total passing) against mocked HTTP responses,
  verifying request shape (headers, payload structure) and the
  fail-fast behavior when a required API key is missing — none of this
  needed real credentials.

## Not yet done

- The actual live Finnish-quality comparison — `chitti/.env` doesn't
  exist yet on this machine. Waiting on the product owner to create it
  locally (never pasted into chat) with real `OPENAI_API_KEY`/
  `ANTHROPIC_API_KEY` values before `scripts/benchmark_finnish.py` can
  run for real.
- Updating the AI backend decision itself (architecture.md,
  risk register #7) with the actual measured result — that's the next
  step once the live run happens.
