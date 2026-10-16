# 0034 — Everyday Companion: the third mode

Date: 2026-10-16
Status: Accepted

## Context

A product-roadmap review argued math and storytelling are two good
*experiences*, but there's no everyday-conversation layer connecting
them -- a child who just wants to chat, play a simple game, ask "why
do spiders make webs," or say "I'm bored" has nowhere to go today.
It listed 5 missing pieces: everyday conversation, Finnish/bilingual
support, games, curiosity, and emotional/social moments.

**The 5 items collapse into two buckets.** Everyday conversation,
games, curiosity, and emotional/social moments (4 of the 5) are all,
at root, the same thing: one well-designed companion prompt with a
broader repertoire than "teach me something." All four are cheap,
prompt-only work. Finnish/bilingual support is correctly flagged as
"core," but it's a genuinely bigger, already-known gap -- Whisper STT
is hardcoded to `language="en"` (decision 0020), `ChildProfile` has
no language field, and Finnish quality has never been independently
verified (the risk register already says it must be measured before
any pilot, not assumed). **Explicitly deferred to its own follow-up
plan**, not bundled here -- it needs real audio testing on the Pi,
which only the product owner can run, plus actual STT/profile
plumbing changes, not a prompt tweak.

**Mode shape**: a new third mode, confirmed with the product owner
rather than assumed, specifically to respect the standing "don't
touch the learning part" instruction literally --
`TEACHABLE_FRIEND_SYSTEM_PROMPT` and `_run_teachable_friend()` are
untouched by this decision.

## What shipped

- **`build_everyday_companion_prompt(child_age=None)`**
  (`conversation/prompts.py`): casual chat (respond naturally, don't
  turn "I'm bored" into an activity), simple games (guess-the-animal,
  would-you-rather, riddles, make-believe -- adapt difficulty, go
  with a child-initiated rule change rather than insisting on how it
  started), spontaneous curiosity (say you're not sure rather than
  inventing a fact, same pattern decision 0016 already proved for
  Story Companion), and the same "vary your moves, don't always ask"
  instruction as decision 0032. Reuses `_age_band_guidance()`
  (already generic).
- **`_trusted_adult_guidance()`** extracted from `_story_companion_
  core()`'s existing emotional-disclosure instruction -- it already
  existed, just nowhere outside Story Companion, even though "I'm
  sad" or "my friend won't play with me" can come up in any
  conversation. Pure DRY refactor: Story Companion's behavior is
  byte-for-byte unchanged, and this doesn't touch Teachable-Friend.
- **`ConversationService.everyday_companion_reply()`**: same
  math_check reuse as `teachable_friend_reply()` -- a stray "2 plus 2
  is 4" during casual chat still gets verified, without duplicating
  decision 0024-0029's logic.
- **`_run_everyday_companion()`** (`voice_loop_demo.py`): same
  math-check wiring (`_resolve_math_check`/`_update_challenge_state`/
  `_patch_if_still_unresolved`/`extract_posed_challenge` -- all
  already free functions) and engagement recording as mode 1, with a
  new `EngagementMode.EVERYDAY_COMPANION`. No `_remember_taught_fact()`
  call -- nothing is being "taught" here in that sense.
- Menu gained `"3) Just Chat (talk, play, wonder, or share your
  day)"`; modes 1 and 2's menu text and default dispatch are
  unchanged.

## Consequences

13 new unit tests (213 total passing): the new prompt's four
guidance areas plus age tuning, the service method's math_check
reuse, and the engagement mode round-trip. No full-loop test for
`_run_everyday_companion()`, consistent with modes 1 and 2 never
being unit-tested end-to-end (push-to-talk I/O).

## Not yet done

Finnish/bilingual support, named above as the correctly-flagged
"core requirement" this decision deliberately didn't touch -- tracked
as a separate follow-up, not forgotten. This mode's prompt is also
untested against a real LLM in practice yet; same honesty-about-
limits as every other prompt-only fix this session.
