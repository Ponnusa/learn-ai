# 0116 — Replace the phonics hint ladder with slow/medium/fast word exposure

Date: 2026-10-26
Status: Accepted

## Context

Direct feedback, after several rounds of fixing bugs in the phonics
hint ladder and its recorded-sound-clip infrastructure (decisions
0112-0115) and discussing whether TTS could even generate reliable
isolated phoneme audio at all (it can't -- no engine checked gives
real control over isolated phoneme pronunciation the way a dedicated
phonics recording does):

> "lets remove the phonics teaaching or reading from chitti, i mean
> dont use the mp3 at all.. lets keep it simple... chitti can juts
> say the word and lets see f the kid understands... can it say this
> word bit slower and then medium and faster for the child to
> understand."

Scoped with two follow-up questions before touching anything:

1. Replace the whole graduated hint ladder (4 escalating phonics
   hints when a word is missed) with "just say the word slow, then
   medium, then fast" -- **yes, entirely**, not just drop its audio
   clips and keep the hint text.
2. The "missing letters" word game (decision 0057/0112/0114) is a
   separate feature and stays as-is, phonics sound clips and all.

Mid-implementation, found a real consequence neither question
covered: `_run_word_family_practice()` (the "want to try a few more
words like it?" bonus) was only ever triggered from inside the hint
ladder's own "resolved on an early stage" branch -- removing that
branch left it with zero callers at all, fully orphaned. Asked a
third, narrower question: **keep it, but trigger it on any correct
retry now** (not gated on the old echo-vs-independent-decoding
distinction, since that distinction no longer exists in the
simplified flow).

## What shipped

**`voice_loop_demo.py`**: the hint ladder's inner 4-stage loop
(`build_hint_line()`'s escalating hints, real phonics clip playback)
is replaced with: speak the missed word three times --
`speed * _WORD_SLOW_SPEED_MULTIPLIER` (0.6), `speed` (the child's own
normal pace), `speed * _WORD_FAST_SPEED_MULTIPLIER` (1.3) -- using
`OpenAITTSBackend`'s already-existing `speed` parameter, no new audio
pipeline at all. Then captures one attempt and reacts: "There you
go!" if correct, `'That's okay! The word is "X". Let's keep going!'`
if not -- no escalation, no second round. The word's own in-story
highlight (decision 0113) is unchanged; only the TEACHING step
underneath it changed.

Since every attempt now comes right after hearing the word said in
full, this never feeds mastery evidence (same "echo isn't evidence"
principle decisions 0065/0066 already established for the old
ladder's own final, told-outright stage -- now *every* attempt is
that case) -- the `retry_evidence_accum` bookkeeping that used to
collect it is removed entirely, not just left empty. Word-family
practice is still offered on a correct retry (per the third
clarifying question), explicitly without that same decoding-
independence gate.

`_give_brief_callout()` (decision 0103's lighter tier, for sentences
that didn't make the session's limited full-correction budget) also
stopped playing a real phonics clip after naming the word, for the
same reason -- consistent with the rest of the correction flow no
longer teaching phonics or touching any sound clip.

**`reading/hints.py`**: `build_hint_line()`, `HINT_STAGES`, and the
now-unused `_first_grapheme()` helper removed. `pick_hint_word()`/
`pick_hint_words()` (deciding WHICH word(s) need attention -- unaffected,
still miscue-based) and `blend_breakdown()`/`_SOUND_EXAMPLES` (still
used by `reading/word_game.py`'s own wrong-answer explanation, an
untouched, separate feature) are unaffected.

**Untouched, per the explicit scoping**: the missing-letters word
game (`_run_word_game()`) and its own real phonics-sound reinforcement
for a wrong answer; `_run_word_family_practice()`'s own wrong-word
phonics reinforcement (only its *trigger condition* changed, not its
internals).

## Consequences

Removed 5 now-obsolete tests (4 `build_hint_line` stage tests in
`test_reading_hints.py`; `test_run_reading_partner_final_stage_resolution_does_not_feed_mastery`,
whose whole premise -- a stage-based echo/independent-decoding
distinction -- no longer exists). Rewrote the hint-retry tests in
`test_voice_loop_demo_intent.py` for the new one-exposure-one-check
shape and the "opportunities == 1, not 2" mastery consequence;
renamed two tests whose old names described the removed 4-stage
escalation. The word-family-practice and reread-miscue tests needed
their own capture-count fixes (one retry attempt instead of up to
four) but no behavioral rewrite, since their own concerns were
unaffected.

Full suite: 720 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

The slow/medium/fast speed multipliers (0.6/1.0/1.3) are a starting
guess, not tuned against real sessions -- if the pacing feels off in
practice, they're one-line constants to adjust. `reading/phonics_audio.py`'s
recorded clips and `DEFERRED_GRAPHEMES` gaps remain exactly as they
were -- still used by the word game and word-family practice, just
no longer by this correction flow.
