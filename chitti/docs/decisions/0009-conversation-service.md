# 0009 — ConversationService: Teachable-Friend, Story Companion, repeat-after-me

Date: 2026-10-13
Status: Accepted

## Context

Fourth real feature, built while the live Finnish benchmark (decision
0008) is still pending `.env` setup on the product owner's machine.
Chosen because it's independent of that blocker — built against the
`LanguageModelBackend` interface with a fake test double, not a real
backend, so it doesn't need to wait.

## What was built

- `conversation/prompts.py`: `TEACHABLE_FRIEND_SYSTEM_PROMPT` (curious-
  peer persona, any topic but age-appropriate, never claims to be
  human, never pressures secrecy) and `build_story_companion_prompt()`
  (embeds the full story transcript with an explicit "use ONLY this
  story" instruction).
- `conversation/service.py`: `ConversationService` — `teachable_friend_reply()`
  and `story_companion_reply()` call the `LanguageModelBackend`, then
  both pass the result through `safety.checks.check_speech()` before
  returning it. `repeat_after_me()` skips the LLM call entirely — it's
  just `check_speech()` then echo-or-decline, since there's nothing to
  generate.
- 6 new unit tests (53 total passing) using a `FakeLanguageModelBackend`
  test double that records every call it receives. Two of them prove
  something that matters more than "the code runs": configuring the
  fake backend to return *unsafe* text (parent-secrecy pressure,
  profanity) still gets blocked by the service — proving the
  screening isn't just present in the code, it actually overrides what
  the "model" said, which is the whole point of spec section 5.

## Consequences

- Risk register #3b, #3c, #12 updated. #3c specifically: the prompt
  grounding is built and tested, but whether a *real* model actually
  honors "use only this story" reliably is explicitly still unverified
  — that needs a live backend, not just confirming the prompt reaches
  it correctly.

## Not yet done

- Wiring any of this into real audio I/O (waits for Milestone 2
  hardware) or a tool-call allowlist (no chitti-specific tools are
  defined yet).
- Live verification of Story Companion's grounding against a real
  model's actual behavior, and the Finnish benchmark itself — both
  still pending real backend use.
