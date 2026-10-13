# 0011 — Finnish benchmark: first live run, a real encoding bug, and a credential-exposure incident

Date: 2026-10-13
Status: Accepted (partial result — not a final backend decision)

## Context

Decision 0008 built both `LanguageModelBackend` implementations and
`scripts/benchmark_finnish.py`, pending the product owner setting up
`.env` with real API keys. This record covers what happened once keys
were actually provided.

## A credential-exposure incident, recorded plainly

Setting this up took several back-and-forth attempts: the product
owner first referenced a key added "to the Pi" (a different, remote
machine not reachable from this session), then pasted both real API
keys directly into the chat after being explicitly asked not to.

**This is logged as risk register #17.** Both keys must be treated as
exposed and rotated by the product owner — nothing this codebase does
changes that; the exposure is in the chat transcript, not in anything
stored here. `chitti/.env` itself was confirmed gitignored via `git
check-ignore` before anything else happened, and was never committed.
No key value appears in this decision record, the risk register, or
any other committed file.

## The actual benchmark result

- **OpenAI**: the pasted key was truncated mid-paste (a terminal
  line-wrap artifact) — every call returned `401 Unauthorized`. This is
  **not** a real signal about OpenAI's Finnish capability; it's
  inconclusive until run again with a complete, valid key.
- **Claude** (`claude-haiku-4-5-20251001`): all 4 prompts succeeded with
  coherent, warm, grammatically plausible Finnish. Notably, the
  Teachable-Friend-style prompt ("I'm teaching you that dogs have a
  good sense of smell") got a genuine, unprompted follow-up question
  back ("Onko sinulla koira, vai tunnetko jonkun, jolla on koira?") —
  the persona behavior from `conversation/prompts.py` held up against
  a real model, not just the fake backend used in decision 0009's
  tests. Latency: 1.24s-4.46s per call — within the spec's ~1s target
  for short replies, well over it for a story-generation request.

**This is a single run, read by a non-Finnish-speaking agent.** It's
evidence Claude's Finnish is *plausible*, not a confirmed verdict —
risk register #7 is updated to reflect "partially verified, needs
native-speaker review," not "resolved."

## A real bug found and fixed along the way

The first run crashed with `UnicodeEncodeError` on Claude's reply (it
contained an emoji), and separately printed every Finnish prompt with
mangled diacritics in the OpenAI error output. Both are the same root
cause: Windows' console defaults to the `cp1252` codepage, which can't
encode either Finnish letters or many emoji. Fixed by adding
`sys.stdout.reconfigure(encoding="utf-8")` at the top of `main()` in
`scripts/benchmark_finnish.py`. Unrelated to either API — would have
hit any script printing non-ASCII text to a default Windows console.

## Not yet done

- A real OpenAI-side result — needs a complete, valid (and, given the
  exposure above, freshly rotated) key.
- Native Finnish-speaker review of Claude's output above.
- Any actual backend decision — this is one data point, not a
  conclusion. Decision 0004's recommendation (provider-neutral
  interface, decide once both sides are measured) still stands.
