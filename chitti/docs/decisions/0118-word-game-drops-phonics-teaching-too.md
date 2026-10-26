# 0118 — The word game drops its own phonics breakdown and sound clips too

Date: 2026-10-26
Status: Accepted

## Context

Direct follow-up to decision 0116: "remove the text explanation and
phonics teaching." When decision 0116 removed the phonics hint
ladder, the missing-letters word game was explicitly kept as-is
(including its own phonics reinforcement), on the strength of an
earlier answer in that same scoping conversation. Pointed at again
from a real session log, where a wrong answer in the word game got:
"For 'hen,' the correct breakdown is 'h' like in 'hat', 'e' like in
'bed', and 'n' like in 'net'." Given the overall direction, the
answer changed: drop it here too, so the word game is no longer the
one remaining place in the reading flow that still teaches phonics.

## What shipped

**`reading/word_game.py`**: `build_word_game_reaction_prompt()` no
longer hands `hints.py`'s own `blend_breakdown()` text to the model
for a wrong word -- each wrong entry is now just `'"word": incorrect.
The real word is "word".'`, and the prompt's own instructions drop
"and its breakdown exactly as given" in favor of "no phonics
breakdown, no sounding it out, just the word itself."

**`voice_loop_demo.py`'s `_run_word_game()`**: no longer calls
`_play_real_phonics_sounds()` for a wrong word after the LLM's
reaction -- the real recorded clip playback decision 0091 added here
is gone.

`incorrect_response()`/`blend_breakdown()` themselves are untouched
-- still used by `_run_word_family_practice()` (decision 0084), a
separate feature this decision doesn't touch.

## Consequences

Updated `test_build_word_game_reaction_prompt_states_correctness_as_given_fact()`
to check for the plain "the real word is X" phrasing and assert no
phonics breakdown text appears. Renamed and rewrote
`test_run_word_game_plays_real_phonics_sounds_for_a_wrong_answer()` to
`..._no_longer_plays_phonics_sounds_for_a_wrong_answer()`, asserting
zero real clips play now.

Full suite: 721 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

Nothing else in the reading flow is known to still teach phonics or
play a recorded sound clip in the child-facing correction/reaction
path -- `_run_word_family_practice()`'s own wrong-word reinforcement
is the only remaining real-clip playback left anywhere, and it
wasn't raised as something to change in this round.
