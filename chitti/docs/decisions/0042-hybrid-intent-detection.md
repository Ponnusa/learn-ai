# 0042 — Hybrid intent detection and mode-switching

Date: 2026-10-17
Status: Accepted

## Context

Previously-deferred gap (memory `chitti-mode-switching-deferred`, noted
during decision 0034's review): mode choice only ever happened once, at
`main()`'s typed menu -- none of the four mode loops in
`voice_loop_demo.py` could hand off to another mode mid-conversation.
If a child said "tell me a story" while in Just Chat, Chitti could only
talk *about* wanting to, with no way to actually switch into Story
Companion's code path.

Confirmed approach (via AskUserQuestion this session):
1. **Detection**: deterministic phrase-matching first; LLM
   classification only as a fallback, not on every turn.
2. **Disambiguation** (multiple stories/lullabies): Chitti speaks the
   choices, the child answers by voice, fuzzy-matched against the
   titles.

**Cost-control refinement found while designing this**, worth flagging
since it narrows the literal two-tier framing the question used: a
design that calls the LLM classifier whenever a turn isn't an exact
phrase match would hit the classifier on nearly *every* ordinary
conversational turn (almost nothing is an exact phrase match), roughly
doubling API cost and per-turn latency for normal conversation, not
just switch-like phrasing. A third, still-deterministic tier fixes
this: a turn only reaches the LLM classifier if it mentions at least
one loose activity keyword ("story", "song", "sing", "lullaby", "chat",
"talk", "teach", "music", ...); a turn with none of those skips the
LLM entirely, for free. Real switch requests almost always name the
activity, so this keeps the "only ambiguous phrasing costs an extra
call" property that was actually asked for.

## What shipped

**New `intent/` package** (`router.py`), parallel in style to
`education/math_check.py`: pure functions, no LLM/IO, returns `None`
rather than guessing.
- `detect_intent_phrase(text) -> str | None`: compiled regexes for
  clear phrasings, returning one of `STORY`/`SONG`/`CHAT`/`TEACH`.
- `mentions_activity_keyword(text) -> bool`: the loose gate controlling
  whether the LLM fallback is even worth calling.

**LLM fallback on `ConversationService`**: new `classify_intent(text)`,
one cheap `generate_reply()` call with a new
`INTENT_CLASSIFIER_SYSTEM_PROMPT` (`conversation/prompts.py`) asking
for exactly one label. Deliberately **not** screened through
`check_speech()` -- its output is never spoken, only used for routing,
same reasoning `summarize_session()` already uses for its own
non-spoken call.

**Orchestration in `voice_loop_demo.py`**: `_detect_switch_intent(text,
conversation)` runs the three tiers in order and maps the result
through `_INTENT_TO_MODE_CHOICE` (`{"STORY": "2", "SONG": "4", "CHAT":
"3", "TEACH": "1"}` -- reuses `main()`'s own menu-choice strings rather
than a parallel enum). Each of `_run_teachable_friend`/
`_run_everyday_companion`/`_run_story_companion`'s turn loops now call
this right after capturing (non-empty) speech and before appending it
to the conversation; a detected switch `break`s the loop -- the
existing `finally` cleanup (summarize, record engagement, save
transcript) still runs exactly as before, over whatever turns happened
before the switch -- and the function returns the next mode code
instead of `None`.

`main()`'s dispatch became a small loop instead of one-shot
`if/elif`, re-dispatching on whatever a mode function returns until one
returns `None`. Ctrl-C is unaffected: it's an exception, not a return
value, so it still propagates straight through to `main()`'s existing
outer `except` -- only a *detected* switch loops back automatically.
Natural completion or "no items yet" still ends the program exactly as
before (no behavior change there).

**Voice-based disambiguation, replacing the typed picker everywhere**
(confirmed via AskUserQuestion -- deliberately not kept as two separate
code paths): `_resolve_spoken_choice(spoken, items)` tries an exact
title substring match, then ordinal words ("first"/"1st"/"one" -> index
0), then `difflib` fuzzy matching, then defaults to the first item
rather than failing. `_pick_item_by_voice(items, label, tts, stt,
audio, face, speed)` skips the question entirely for a single item;
for multiple, speaks "I have N {label}: A, B. Which one would you
like?", listens for an answer, resolves it, with one spoken retry
before defaulting. `_run_story_companion` and `_run_lullaby_time` both
now call this instead of `input("Pick a story/lullaby: ")` -- this
changes today's typed-menu-entry behavior too, not just the new
mid-conversation switch path. `_run_lullaby_time` gained an `stt`
parameter for this (it had none before).

## Consequences

23 new unit tests (277 total passing, 1 skipped where noted in decision
0040): `test_intent_router.py` (phrase/keyword coverage),
`test_conversation_service.py` additions (`classify_intent()`,
including that its output is never screened through `check_speech()`),
`test_voice_loop_demo_intent.py` (`_detect_switch_intent`'s three
tiers -- including proving the no-keyword case never calls the LLM at
all -- `_resolve_spoken_choice`, `_pick_item_by_voice`, and one
end-to-end test driving `_run_teachable_friend` through an ordinary
turn followed by a switch-triggering one, asserting the returned mode
code and that the `finally` cleanup still recorded the ordinary turn).

## Addendum (2026-10-17): stuck restarting the mode it was already in

Found live via `intent_demo.py`: saying "I want to teach you
mathematics, I want to be the teacher" *while already in
Teachable-Friend mode* correctly matched the TEACH intent -- but
`_detect_switch_intent` had no check against the mode already
running, so this was treated as a "switch" to the mode already
active. Every single teaching statement restarted Teachable-Friend
from scratch (re-printing its banner, discarding the in-progress turn)
instead of ever reaching `teachable_friend_reply()` -- an infinite
non-progress loop, since teaching Chitti something naturally involves
saying "teach".

Fixed by giving `_detect_switch_intent` a `current_mode` parameter
(each caller passes its own fixed mode code -- `"1"` from
`_run_teachable_friend`, `"3"` from `_run_everyday_companion`, `"2"`
from `_run_story_companion`) and suppressing a match equal to it,
regardless of which tier produced it. Applied uniformly to all three
modes, not just Teachable-Friend, since the same class of bug would
otherwise resurface anywhere (e.g. "let's just chat" said while
already in Just Chat would otherwise also restart it, discarding
history for no reason). 2 new regression tests cover both tiers: the
strict-phrase case and the LLM-fallback case each being suppressed
when they resolve to the mode already running (279 total passing, 1
skipped).

## Addendum (2026-10-17): switching ate the utterance that triggered it

Found live via `intent_demo.py`: saying "Let me teach you something"
switched into Teachable-Friend correctly, but then went silent,
waiting for a fresh capture -- the child had to say the exact same
thing a second time before Chitti ever replied to it. Same for
switching back out: "...that's why I am sad" switched into Just Chat
silently, requiring a repeat before getting a response. The triggering
utterance itself was being thrown away at the moment of switching,
since the mode loops only ever broke with `next_mode`, never carrying
the text that caused the break anywhere.

Fixed by having `_run_teachable_friend`/`_run_everyday_companion`/
`_run_story_companion` return `(next_mode, switch_trigger_text)`
instead of just `next_mode`, and giving each an `initial_text`
parameter: when set, the function skips its first capture and
processes that text as a genuine first turn instead. `_run_story_
companion` accepts the parameter for calling-convention uniformity but
doesn't use it (it always starts with a fixed pick-story/read-story/
generate-opening sequence, not a reply to an arbitrary line).
`run_mode_dispatch_loop()` threads `carried_text` between mode calls,
clearing it whenever lullaby time (no listening turn to carry into)
is dispatched. `DemoContext`/`setup_demo()` from decision 0043 were
unaffected. 2 new/updated tests, including one proving the carried-
over turn reaches the mode's own reply-generation call without ever
invoking `_capture_and_transcribe()` again (280 total passing, 1
skipped).

This directly produces the "warm, continuous-feeling" transition the
product owner asked for, for free: the mode's own real system prompt
replies to the actual triggering sentence (e.g. Teachable-Friend's
"Oh, I love learning new things! What do you want to teach me?"),
rather than needing a separate canned acknowledgment message bolted on
at switch time.

## Not yet done

No mid-lullaby interruption (lullaby playback has no listening turn to
interrupt in this pass). Switching doesn't resume the *previous*
mode's conversational state -- it starts the new mode fresh, same as
entering it from the top-level menu; returning to exactly where a
conversation left off isn't built. No handling for a single utterance
naming two intents at once ("stop the story and teach you something").
The LLM fallback adds a real new failure surface (a network/API error
on `classify_intent()` can now interrupt an otherwise-ordinary turn
that happens to mention an activity keyword) -- no new retry/resilience
was added, consistent with this project's existing posture elsewhere
(no network resiliency built for any other LLM call either).
